import json
import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict
import asyncio

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionType(Enum):
    PLAN = "plan"
    RETRIEVE = "retrieve"
    ACT = "act"
    VERIFY = "verify"
    RESPOND = "respond"


@dataclass
class OrchestrationStep:
    step_id: int
    action_type: ActionType
    description: str
    status: StepStatus = StepStatus.PENDING
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None


@dataclass
class OrchestrationContext:
    session_id: str
    tenant_id: str
    user_message: str
    conversation_history: List[Dict[str, str]]
    available_tools: List[str]
    max_steps: int = 10
    current_step: int = 0
    steps: List[OrchestrationStep] = None
    final_response: Optional[str] = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = []


class AgentOrchestrator:
    def __init__(self, llm_client, tools_registry=None, rag_system=None):
        self.llm_client = llm_client
        self.tools_registry = tools_registry
        self.rag_system = rag_system
        self.max_retries = 3

    async def orchestrate(self, context: OrchestrationContext) -> Dict[str, Any]:
        """Main orchestration loop: Plan -> Retrieve -> Act -> Verify -> Respond"""
        logger.info(f"Starting orchestration for session {context.session_id}")

        try:
            # Step 1: Plan
            await self._execute_step(context, ActionType.PLAN, "Analyze user request and create execution plan")

            # Step 2: Retrieve (if needed)
            if self._needs_retrieval(context):
                await self._execute_step(context, ActionType.RETRIEVE, "Retrieve relevant information")

            # Step 3: Act (may involve multiple sub-actions)
            await self._execute_step(context, ActionType.ACT, "Execute planned actions")

            # Step 4: Verify
            await self._execute_step(context, ActionType.VERIFY, "Verify results and check for completeness")

            # Step 5: Respond
            await self._execute_step(context, ActionType.RESPOND, "Generate final response")

            return self._build_response(context)

        except Exception as e:
            logger.error(f"Orchestration failed: {str(e)}")
            return self._build_error_response(context, str(e))

    async def _execute_step(self, context: OrchestrationContext, action_type: ActionType, description: str):
        """Execute a single orchestration step"""
        if context.current_step >= context.max_steps:
            logger.warning(f"Max steps ({context.max_steps}) reached, halting orchestration")
            return

        context.current_step += 1
        step = OrchestrationStep(
            step_id=context.current_step,
            action_type=action_type,
            description=description,
            status=StepStatus.RUNNING
        )
        context.steps.append(step)

        try:
            if action_type == ActionType.PLAN:
                await self._plan_step(context, step)
            elif action_type == ActionType.RETRIEVE:
                await self._retrieve_step(context, step)
            elif action_type == ActionType.ACT:
                await self._act_step(context, step)
            elif action_type == ActionType.VERIFY:
                await self._verify_step(context, step)
            elif action_type == ActionType.RESPOND:
                await self._respond_step(context, step)

            step.status = StepStatus.COMPLETED
            logger.info(f"Step {step.step_id} ({action_type.value}) completed successfully")

        except Exception as e:
            step.status = StepStatus.FAILED
            step.error_message = str(e)
            logger.error(f"Step {step.step_id} ({action_type.value}) failed: {str(e)}")
            raise

    async def _plan_step(self, context: OrchestrationContext, step: OrchestrationStep):
        """Plan step: Analyze user request and determine what needs to be done"""
        planning_prompt = f"""
        Analyze the user's request and create a plan to address it.

        User message: {context.user_message}
        Available tools: {', '.join(context.available_tools)}

        Determine:
        1. What information is needed?
        2. What actions should be taken?
        3. What tools are required?

        Respond with a JSON object containing:
        - "needs_retrieval": boolean
        - "required_tools": list of tool names
        - "plan_summary": string description of the plan
        """

        messages = [{"role": "user", "content": planning_prompt}]
        response = await self.llm_client.generate_response(messages)

        try:
            plan_data = json.loads(response["content"])
            step.output_data = plan_data
        except json.JSONDecodeError:
            # Fallback to simple plan
            step.output_data = {
                "needs_retrieval": False,
                "required_tools": [],
                "plan_summary": "Generate a helpful response to the user's question"
            }

    async def _retrieve_step(self, context: OrchestrationContext, step: OrchestrationStep):
        """Retrieve step: Get relevant information from knowledge base or external sources"""
        if not self.rag_system:
            step.output_data = {
                "retrieved_info": "No RAG system available",
                "sources": []
            }
            return

        try:
            # Retrieve relevant information using RAG system
            results, session_context = await self.rag_system.retrieve_with_context(
                context.user_message,
                context.session_id,
                limit=3
            )

            retrieved_info = []
            sources = []

            for result in results:
                retrieved_info.append({
                    "content": result.content,
                    "source": result.source,
                    "relevance_score": result.relevance_score,
                    "metadata": result.metadata
                })
                sources.append(result.source)

            step.output_data = {
                "retrieved_info": retrieved_info,
                "sources": list(set(sources)),  # Unique sources
                "session_context_items": len(session_context)
            }

            # Add current conversation to RAG system for future retrieval
            if context.conversation_history:
                last_user_msg = None
                last_assistant_msg = None

                for msg in reversed(context.conversation_history):
                    if msg["role"] == "user" and not last_user_msg:
                        last_user_msg = msg["content"]
                    elif msg["role"] == "assistant" and not last_assistant_msg:
                        last_assistant_msg = msg["content"]

                    if last_user_msg and last_assistant_msg:
                        break

                if last_user_msg and last_assistant_msg:
                    await self.rag_system.add_conversation_turn(
                        context.session_id,
                        last_user_msg,
                        last_assistant_msg
                    )

        except Exception as e:
            logger.error(f"Error in retrieve step: {e}")
            step.output_data = {
                "retrieved_info": f"Error retrieving information: {str(e)}",
                "sources": []
            }

    async def _act_step(self, context: OrchestrationContext, step: OrchestrationStep):
        """Act step: Execute the planned actions using available tools"""
        plan_data = None
        for s in context.steps:
            if s.action_type == ActionType.PLAN and s.output_data:
                plan_data = s.output_data
                break

        if not plan_data:
            step.output_data = {"action_taken": "No plan available, proceeding with direct response"}
            return

        required_tools = plan_data.get("required_tools", [])
        actions_taken = []

        if not self.tools_registry:
            # Fallback to old behavior
            for tool in required_tools:
                actions_taken.append(f"Tool {tool} not available (no tools registry)")
        else:
            # Use tools registry to execute tools
            for tool_name in required_tools:
                try:
                    # For web search, extract query from user message
                    if tool_name == "web_search":
                        result = await self.tools_registry.execute_tool(
                            tool_name,
                            {"query": context.user_message, "max_results": 3},
                            context.tenant_id
                        )

                        if result.get("success"):
                            actions_taken.append(
                                f"Executed {tool_name}: found {result.get('total_results', 0)} results")
                            # Store results for use in response generation
                            step.output_data = step.output_data or {}
                            step.output_data["search_results"] = result.get("results", [])
                        else:
                            actions_taken.append(
                                f"Failed to execute {tool_name}: {result.get('error', 'Unknown error')}")

                    else:
                        # Generic tool execution
                        result = await self.tools_registry.execute_tool(
                            tool_name,
                            {"query": context.user_message},
                            context.tenant_id
                        )

                        if result.get("success"):
                            actions_taken.append(f"Executed {tool_name} successfully")
                        else:
                            actions_taken.append(
                                f"Failed to execute {tool_name}: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    actions_taken.append(f"Error executing {tool_name}: {str(e)}")

        step.output_data = {
            "actions_taken": actions_taken,
            "tools_used": required_tools,
            **(step.output_data or {})
        }

    async def _verify_step(self, context: OrchestrationContext, step: OrchestrationStep):
        """Verify step: Check if the actions were successful and complete"""
        verification_prompt = f"""
        Review the execution steps and determine if the user's request has been adequately addressed.

        User request: {context.user_message}
        Steps taken: {[s.description for s in context.steps[:-1]]}

        Respond with a JSON object:
        - "is_complete": boolean
        - "confidence": number (0-1)
        - "missing_info": list of any missing information
        """

        messages = [{"role": "user", "content": verification_prompt}]
        response = await self.llm_client.generate_response(messages)

        try:
            verification_data = json.loads(response["content"])
            step.output_data = verification_data
        except json.JSONDecodeError:
            step.output_data = {
                "is_complete": True,
                "confidence": 0.8,
                "missing_info": []
            }

    async def _respond_step(self, context: OrchestrationContext, step: OrchestrationStep):
        """Respond step: Generate the final response to the user"""
        # Gather context from all previous steps
        execution_summary = []
        for s in context.steps[:-1]:  # Exclude current step
            if s.output_data:
                execution_summary.append(f"{s.action_type.value}: {s.output_data}")

        response_prompt = f"""
        Generate a helpful response to the user based on the execution context.

        User message: {context.user_message}
        Execution summary: {execution_summary}

        Provide a clear, helpful response that addresses the user's request.
        """

        messages = context.conversation_history + [{"role": "user", "content": response_prompt}]
        response = await self.llm_client.generate_response(messages)

        context.final_response = response["content"]
        step.output_data = {
            "final_response": context.final_response,
            "tokens_used": int(response.get("tokens_used", 0))
        }

    def _needs_retrieval(self, context: OrchestrationContext) -> bool:
        """Determine if retrieval step is needed based on the plan"""
        for step in context.steps:
            if step.action_type == ActionType.PLAN and step.output_data:
                return step.output_data.get("needs_retrieval", False)
        return False

    def _build_response(self, context: OrchestrationContext) -> Dict[str, Any]:
        """Build the final orchestration response"""
        total_tokens = sum(
            int(step.output_data.get("tokens_used", 0))
            for step in context.steps
            if step.output_data and "tokens_used" in step.output_data
        )

        return {
            "response": context.final_response or "I apologize, but I couldn't generate a response.",
            "steps": [asdict(step) for step in context.steps],
            "tokens_used": total_tokens,
            "status": "success",
            "session_id": context.session_id
        }

    def _build_error_response(self, context: OrchestrationContext, error_message: str) -> Dict[str, Any]:
        """Build error response"""
        return {
            "response": f"I encountered an error while processing your request: {error_message}",
            "steps": [asdict(step) for step in context.steps],
            "tokens_used": 0,
            "status": "error",
            "error": error_message,
            "session_id": context.session_id
        }
