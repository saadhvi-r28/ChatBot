import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Bot, User, Settings, Trash2, History, MessageSquare, RotateCcw, Plus, CheckSquare, Square, AlertCircle } from 'lucide-react';

// Model options - same as the original Streamlit app
const MODELS = {
  'Fast (3B)': 'llama3.2:3b',
  'Balanced (8B)': 'deepseek-r1:8b',
  'Fast (1B)': 'llama3.2:1b',
};

const DEFAULT_MODEL = 'Fast (3B)';

function App() {
  const [messages, setMessages] = useState([
    {
      role: "system",
      content: `You are an AI assistant designed to help 
      cybersecurity analysts investigate and respond to alerts triggered in a 
      SIEM (Security Information and Event Management) system. 
      Your role is to assist with incident triage, provide relevant context, 
      suggest next steps, reference past incidents, explain log data, and recommend playbooks 
      or actions for containment, eradication, and recovery. 
      Always provide clear, concise, and technically sound responses. Prioritize accuracy, 
      use threat intelligence where relevant, and help analysts make quick and informed decisions.
      If needed, ask clarifying questions to refine your recommendations.
      You are also a helpful assistant that can answer questions about the 
      SIEM system and the alerts.
      Keep responses concise and to the point.`
    }
  ]);
  
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [enableStreaming, setEnableStreaming] = useState(true);
  const [maxTokens, setMaxTokens] = useState(500);
  const [error, setError] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [checklistItems, setChecklistItems] = useState([]);
  const [showChecklist, setShowChecklist] = useState(false);
  
  const chatContainerRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  // Load conversation sessions on component mount
  useEffect(() => {
    loadSessions();
  }, []);

  // Extract checklist items from AI responses
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.role === 'assistant') {
      const checklistItems = extractChecklistItems(lastMessage.content);
      if (checklistItems.length > 0) {
        setChecklistItems(checklistItems);
        setShowChecklist(true);
      }
    }
  }, [messages]);

  const extractChecklistItems = (content) => {
    const checklistRegex = /□\s*(.+?)(?=\n|$)/g;
    const items = [];
    let match;
    
    while ((match = checklistRegex.exec(content)) !== null) {
      items.push({
        id: Date.now() + Math.random(),
        text: match[1].trim(),
        completed: false
      });
    }
    
    return items;
  };

  const toggleChecklistItem = (itemId) => {
    setChecklistItems(prev => 
      prev.map(item => 
        item.id === itemId 
          ? { ...item, completed: !item.completed }
          : item
      )
    );
  };

  const getChecklistProgress = () => {
    if (checklistItems.length === 0) return 0;
    const completed = checklistItems.filter(item => item.completed).length;
    return Math.round((completed / checklistItems.length) * 100);
  };

  const loadSessions = async () => {
    try {
      const response = await axios.get('http://localhost:5001/conversation-history');
      setSessions(response.data.sessions || []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  const loadSessionHistory = async (sessionId) => {
    try {
      const response = await axios.get(`http://localhost:5001/session-history/${sessionId}`);
      
      // Convert history to message format
      const historyMessages = [messages[0]]; // Start with system message
      
      // Handle the flat message array format from backend
      response.data.conversation_history.forEach(msg => {
        historyMessages.push({
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp
        });
      });
      
      setMessages(historyMessages);
      setCurrentSessionId(sessionId);
      setError(null);
      
      // Update selected model to match the session's model
      const sessionModel = response.data.model;
      const modelKey = Object.keys(MODELS).find(key => MODELS[key] === sessionModel);
      if (modelKey) {
        setSelectedModel(modelKey);
      }
      
      // Extract checklist items from the last assistant message
      if (historyMessages.length > 1) {
        const lastAssistantMessage = historyMessages[historyMessages.length - 1];
        if (lastAssistantMessage.role === 'assistant') {
          const extractedItems = extractChecklistItems(lastAssistantMessage.content);
          if (extractedItems.length > 0) {
            setChecklistItems(extractedItems);
            setShowChecklist(true);
          }
        }
      }
    } catch (err) {
      console.error('Failed to load session history:', err);
      setError('Failed to load session history');
    }
  };

  const createNewSession = async () => {
    try {
      const response = await axios.post('http://localhost:5001/new-session', {
        model: MODELS[selectedModel]  // Send current selected model
      });
      
      setCurrentSessionId(response.data.sessionId);
      setMessages([messages[0]]); // Keep system message
      setError(null);
      setChecklistItems([]);
      setShowChecklist(false);
      await loadSessions();
    } catch (err) {
      console.error('Failed to create new session:', err);
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e) => {
    setInputMessage(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = '48px';
    }

    try {
      const response = await axios.post('http://localhost:5001/chat', {
        message: inputMessage.trim(),
        model: MODELS[selectedModel],
        maxTokens,
        enableStreaming,
        messages: messages.slice(-10), // Keep only last 10 messages for context
        sessionId: currentSessionId // Send current session ID
      });

      // Instead of appending assistantMessage, reload full history from backend
      await loadSessionHistory(currentSessionId);

      // Update current session ID if it changed
      if (response.data.sessionId) {
        setCurrentSessionId(response.data.sessionId);
      }

      // Reload sessions after new message
      await loadSessions();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const clearCurrentSession = async () => {
    if (!currentSessionId) return;
    try {
      await axios.post(`http://localhost:5001/clear-session/${currentSessionId}`);
      setMessages([messages[0]]); // Keep system message
      setError(null);
      setChecklistItems([]);
      setShowChecklist(false);
      // Fetch the now-empty chat history for this session
      const response = await axios.get(`http://localhost:5001/session-history/${currentSessionId}`);
      const historyMessages = [messages[0]];
      setMessages(historyMessages);
    } catch (err) {
      console.error('Failed to clear session:', err);
    }
  };

  const clearAllSessions = async () => {
    try {
      await axios.post('http://localhost:5001/clear-all-sessions');
      setMessages([messages[0]]); // Keep system message
      setSessions([]);
      setCurrentSessionId(null);
      setError(null);
      setChecklistItems([]);
      setShowChecklist(false);
    } catch (err) {
      console.error('Failed to clear all sessions:', err);
    }
  };

  const formatMessage = (content) => {
    if (!content) return '';
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br />');
  };

  const truncateText = (text, maxLength = 50) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  const getCurrentSessionTitle = () => {
    const currentSession = sessions.find(s => s.session_id === currentSessionId);
    return currentSession ? currentSession.title : 'New Chat';
  };

  // On session change or refresh, always fetch chat history
  useEffect(() => {
    if (currentSessionId) {
      axios.get(`http://localhost:5001/session-history/${currentSessionId}`)
        .then(response => {
          const historyMessages = [messages[0]]; // Keep system message
          const conv = response.data.conversation_history || [];
          if (conv.length > 0 && conv[0].user !== undefined) {
            // Backend returns exchanges: {user: "...", assistant: "..."}
            conv.forEach(exchange => {
              if (exchange.user) {
                historyMessages.push({ role: 'user', content: exchange.user, timestamp: exchange.timestamp });
              }
              if (exchange.assistant) {
                historyMessages.push({ role: 'assistant', content: exchange.assistant, timestamp: exchange.timestamp });
              }
            });
          } else {
            // Backend returns flat messages: {role: "...", content: "..."}
            conv.forEach(msg => {
              historyMessages.push({
                role: msg.role,
                content: msg.content,
                timestamp: msg.timestamp
              });
            });
          }
          setMessages(historyMessages);
        });
    }
    // eslint-disable-next-line
  }, [currentSessionId]);

  return (
    <div className="app">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="settings-section">
          <h3><Settings size={16} /> Settings</h3>
          
          <div className="setting-item">
            <label htmlFor="model-select">Choose Model:</label>
            <select
              id="model-select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
            >
              {Object.keys(MODELS).map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>

          <div className="setting-item">
            <label>
              <input
                type="checkbox"
                checked={enableStreaming}
                onChange={(e) => setEnableStreaming(e.target.checked)}
              />
              Enable Streaming
            </label>
          </div>

          <div className="setting-item">
            <label htmlFor="max-tokens">
              Max Response Length: {maxTokens} tokens
              <span className="tooltip" title="This ensures responses are complete and coherent within the specified limit. The AI will prioritize the most critical information to fit within this constraint.">
                ℹ️
              </span>
            </label>
            <input
              id="max-tokens"
              type="range"
              min="100"
              max="1000"
              value={maxTokens}
              onChange={(e) => setMaxTokens(parseInt(e.target.value))}
            />
            <div className="token-info">
              <small>
                {maxTokens < 300 ? "Short responses" : 
                 maxTokens < 600 ? "Standard responses" : 
                 "Detailed responses"}
              </small>
            </div>
          </div>

          <div className="button-group">
            <button className="new-chat-button" onClick={createNewSession}>
              <Plus size={14} /> New Chat
            </button>
            <button className="clear-button" onClick={clearAllSessions}>
              <Trash2 size={14} /> Clear All
            </button>
          </div>
        </div>

        {/* Checklist Section */}
        {showChecklist && checklistItems.length > 0 && (
          <div className="checklist-section">
            <div className="checklist-header" onClick={() => setShowChecklist(!showChecklist)}>
              <h4><CheckSquare size={16} /> Incident Checklist ({getChecklistProgress()}%)</h4>
              <span className="toggle-icon">{showChecklist ? '▼' : '▶'}</span>
            </div>
            
            {showChecklist && (
              <div className="checklist-list">
                {checklistItems.map((item) => (
                  <div 
                    key={item.id} 
                    className={`checklist-item ${item.completed ? 'completed' : ''}`}
                    onClick={() => toggleChecklistItem(item.id)}
                  >
                    <div className="checklist-checkbox">
                      {item.completed ? <CheckSquare size={14} /> : <Square size={14} />}
                    </div>
                    <span className="checklist-text">{item.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Conversation Sessions Section */}
        <div className="conversation-history-section">
          <div className="history-header" onClick={() => setShowHistory(!showHistory)}>
            <h4><History size={16} /> Chat Sessions ({sessions.length})</h4>
            <span className="toggle-icon">{showHistory ? '▼' : '▶'}</span>
          </div>
          
          {showHistory && (
            <div className="history-list">
              {sessions.length === 0 ? (
                <p className="no-history">No chat sessions yet.</p>
              ) : (
                sessions.map((session) => (
                  <div 
                    key={session.session_id} 
                    className={`history-session ${currentSessionId === session.session_id ? 'active' : ''}`}
                    onClick={() => loadSessionHistory(session.session_id)}
                  >
                    <div className="session-preview">
                      <MessageSquare size={12} />
                      <span>{truncateText(session.preview, 40)}</span>
                    </div>
                    <div className="session-meta">
                      <span className="session-count">{session.exchange_count} messages</span>
                      <span className="session-time">{session.last_updated}</span>
                    </div>
                    <div className="session-model">
                      <span className="model-badge">{Object.keys(MODELS).find(key => MODELS[key] === session.model) || 'Unknown'}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div className="performance-tips">
          <h4>Performance Tips:</h4>
          <ul>
            <li>Use smaller models (1B/3B) for faster responses</li>
            <li>Reduce max response length</li>
            <li>Clear chat history periodically</li>
            <li>Keep messages concise</li>
          </ul>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        <div className="header">
          <div className="header-left">
            <h1>🤖 Cybersecurity Analyst Assistant</h1>
            <div className="current-model">
              <span className="model-indicator">Model: {selectedModel}</span>
            </div>
            {currentSessionId && (
              <div className="current-session-indicator">
                <span>📝 {getCurrentSessionTitle()}</span>
              </div>
            )}
          </div>
          {currentSessionId && (
            <button className="clear-session-button" onClick={clearCurrentSession}>
              <Trash2 size={14} /> Clear This Chat
            </button>
          )}
        </div>

        {/* Main Chat Area */}
        <div className="chat-container">
          
          <div className="messages-container" ref={chatContainerRef}>
            {error && (
              <div className="error">
                <AlertCircle size={16} />
                {error}
              </div>
            )}
            
            {messages.slice(1).map((message, index) => (
              <div key={index} className={`message ${message.role}`}>
                <div className="message-content">
                  <div className="message-header">
                    <span className="message-role">
                      {message.role === 'user' ? '👤 You' : '🤖 Assistant'}
                    </span>
                    {message.timestamp && (
                      <span className="message-time">{message.timestamp}</span>
                    )}
                  </div>
                  <div 
                    className="message-text"
                    dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }}
                  />
                  {message.responseTime && (
                    <div className="response-time">
                      Response time: {message.responseTime.toFixed(2)}s
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="message assistant">
                <div className="message-content">
                  <div className="message-header">
                    <span className="message-role">🤖 Assistant</span>
                  </div>
                  <div className="message-text">
                    <div className="loading-indicator">
                      <div className="typing-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      Thinking...
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="input-container">
          <form className="input-form" onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}>
            <textarea
              ref={inputRef}
              className="input-field"
              value={inputMessage}
              onChange={handleInputChange}
              onKeyPress={handleKeyPress}
              placeholder="Type your message and press Enter..."
              disabled={isLoading}
              rows={1}
            />
            <button
              type="submit"
              className="send-button"
              disabled={!inputMessage.trim() || isLoading}
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default App; 