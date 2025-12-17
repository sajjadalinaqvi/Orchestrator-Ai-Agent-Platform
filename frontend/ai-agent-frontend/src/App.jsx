import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { ScrollArea } from '@/components/ui/scroll-area.jsx'
import { Separator } from '@/components/ui/separator.jsx'
import { Send, Bot, User, Loader2, Settings, FileText, Search } from 'lucide-react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: 'Hello! I\'m your AI agent. I can help you with various tasks including web search, document analysis, and more. How can I assist you today?',
      timestamp: new Date(),
      steps: []
    }
  ])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showSteps, setShowSteps] = useState({})
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date(),
      steps: []
    }

    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [...messages, userMessage].map(msg => ({
            role: msg.role,
            content: msg.content
          }))
        })
      })

      if (!response.ok) {
        throw new Error('Failed to get response')
      }

      const data = await response.json()

      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
        steps: data.steps || [],
        tokensUsed: data.tokens_used,
        status: data.status
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}`,
        timestamp: new Date(),
        steps: [],
        isError: true
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const toggleSteps = (messageId) => {
    setShowSteps(prev => ({
      ...prev,
      [messageId]: !prev[messageId]
    }))
  }

  const getStepIcon = (actionType) => {
    switch (actionType) {
      case 'plan': return <Settings className="w-3 h-3" />
      case 'retrieve': return <Search className="w-3 h-3" />
      case 'act': return <Bot className="w-3 h-3" />
      case 'verify': return <FileText className="w-3 h-3" />
      case 'respond': return <Send className="w-3 h-3" />
      default: return <Bot className="w-3 h-3" />
    }
  }

  const getStepColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-200'
      case 'running': return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'failed': return 'bg-red-100 text-red-800 border-red-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <Card className="mb-6 shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-gray-800 flex items-center justify-center gap-2">
              <Bot className="w-8 h-8 text-blue-600" />
              AI Agent Platform
            </CardTitle>
            <p className="text-gray-600">Intelligent assistant with orchestration, RAG, and tool integration</p>
          </CardHeader>
        </Card>

        {/* Chat Container */}
        <Card className="shadow-xl">
          <CardContent className="p-0">
            {/* Messages Area */}
            <ScrollArea className="h-[500px] p-4">
              <div className="space-y-4">
                {messages.map((message) => (
                  <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                      {/* Message Bubble */}
                      <div className={`flex items-start gap-2 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                          message.role === 'user'
                            ? 'bg-blue-600 text-white'
                            : message.isError
                              ? 'bg-red-600 text-white'
                              : 'bg-gray-600 text-white'
                        }`}>
                          {message.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                        </div>

                        <div className={`rounded-lg px-4 py-2 ${
                          message.role === 'user'
                            ? 'bg-blue-600 text-white'
                            : message.isError
                              ? 'bg-red-50 text-red-800 border border-red-200'
                              : 'bg-white text-gray-800 border border-gray-200'
                        }`}>
                          <p className="whitespace-pre-wrap">{message.content}</p>

                          {/* Message metadata */}
                          <div className={`text-xs mt-2 flex items-center gap-2 ${
                            message.role === 'user' ? 'text-blue-100' : 'text-gray-500'
                          }`}>
                            <span>{message.timestamp.toLocaleTimeString()}</span>
                            {message.tokensUsed && (
                              <Badge variant="outline" className="text-xs">
                                {message.tokensUsed} tokens
                              </Badge>
                            )}
                            {message.steps && message.steps.length > 0 && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-auto p-1 text-xs"
                                onClick={() => toggleSteps(message.id)}
                              >
                                {showSteps[message.id] ? 'Hide' : 'Show'} Steps ({message.steps.length})
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Steps Details */}
                      {showSteps[message.id] && message.steps && message.steps.length > 0 && (
                        <div className="mt-3 ml-10 space-y-2">
                          {message.steps.map((step, index) => (
                            <div key={index} className="bg-gray-50 rounded-lg p-3 border">
                              <div className="flex items-center gap-2 mb-2">
                                {getStepIcon(step.action_type)}
                                <span className="font-medium text-sm capitalize">{step.action_type}</span>
                                <Badge className={`text-xs ${getStepColor(step.status)}`}>
                                  {step.status}
                                </Badge>
                              </div>
                              <p className="text-sm text-gray-600">{step.description}</p>
                              {step.output_data && (
                                <details className="mt-2">
                                  <summary className="text-xs text-gray-500 cursor-pointer">View Details</summary>
                                  <pre className="text-xs bg-gray-100 p-2 rounded mt-1 overflow-auto">
                                    {JSON.stringify(step.output_data, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {/* Loading indicator */}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-gray-600 text-white flex items-center justify-center">
                        <Bot className="w-4 h-4" />
                      </div>
                      <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                        <div className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span className="text-gray-600">Thinking...</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              <div ref={messagesEndRef} />
            </ScrollArea>

            <Separator />

            {/* Input Area */}
            <div className="p-4">
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message here..."
                  disabled={isLoading}
                  className="flex-1"
                />
                <Button
                  onClick={sendMessage}
                  disabled={isLoading || !inputMessage.trim()}
                  className="px-4"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Press Enter to send, Shift+Enter for new line
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center mt-6 text-sm text-gray-600">
          <p>AI Agent Platform - Powered by orchestration, RAG, and intelligent tools</p>
        </div>
      </div>
    </div>
  )
}

export default App