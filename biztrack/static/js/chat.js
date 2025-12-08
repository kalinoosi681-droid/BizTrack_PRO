// ==============================================================
// FIXED: AI Chat Widget with Lesotho Intelligence
// ==============================================================
class AIChat {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.conversationId = options.conversationId || null;
        this.apiBase = options.apiBase || '/api/ai';
        this.onMessage = options.onMessage || null;
        
        this.init();
    }
    
    init() {
        this.attachEventListeners();
        this.loadConversationHistory();
    }
    
    attachEventListeners() {
        const sendBtn = document.getElementById('ai-chat-send-btn');
        const input = document.getElementById('ai-chat-input');
        const voiceBtn = document.getElementById('ai-chat-voice-btn');
        const form = document.getElementById('ai-chat-form');
        
        // CRITICAL FIX: Prevent form submission
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.sendMessage();
                return false;
            });
        }
        
        if (sendBtn) {
            sendBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.sendMessage();
                return false;
            });
        }
        
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.sendMessage();
                    return false;
                }
            });
        }
        
        if (voiceBtn) {
            voiceBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.startVoiceInput();
            });
        }
    }
    
    async sendMessage() {
        const input = document.getElementById('ai-chat-input');
        const message = input.value.trim();
        
        if (!message) {
            console.warn('Empty message, ignoring');
            return;
        }
        
        console.log('Sending message:', message);
        
        // Add user message
        this.addMessage(message, 'user');
        input.value = '';
        
        // Show typing
        this.showTyping(true);
        
        try {
            await this.getAIResponse(message);
        } catch (error) {
            console.error('Chat error:', error);
            this.addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        } finally {
            this.showTyping(false);
        }
    }

    async getAIResponse(message) {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
        
        console.log('Fetching AI response...');
        
        try {
            const response = await fetch(`${this.apiBase}/chat`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify({
                    query: message,
                    conversation_id: this.conversationId,
                    stream: false
                })
            });
            
            console.log('Response status:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('API Error:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('AI Response data:', data);
            
            if (data.response) {
                this.addMessage(data.response, 'bot');
            } else if (data.error) {
                this.addMessage(`Error: ${data.error}`, 'bot');
            } else {
                this.addMessage("No response received.", 'bot');
            }
            
        } catch (error) {
            console.error('Chat API error:', error);
            throw error;
        }
    }

    addMessage(text, sender) {
        const messagesContainer = document.getElementById('ai-chat-messages');
        
        if (!messagesContainer) {
            console.error('Chat messages container not found!');
            return null;
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message-${sender}`;
        
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${sender === 'user' ? 'user-bubble' : 'ai-bubble'}`;
        bubble.innerHTML = this.formatMessage(text);
        
        messageDiv.appendChild(bubble);
        messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    formatMessage(text) {
        // Basic markdown-like formatting
        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
        text = text.replace(/\n/g, '<br>');
        return text;
    }
    
    showTyping(show) {
        let typingIndicator = document.getElementById('ai-typing-indicator');
        
        if (show && !typingIndicator) {
            const messagesContainer = document.getElementById('ai-chat-messages');
            typingIndicator = document.createElement('div');
            typingIndicator.id = 'ai-typing-indicator';
            typingIndicator.className = 'chat-message-ai';
            typingIndicator.innerHTML = `
                <div class="chat-bubble ai-bubble">
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            `;
            messagesContainer.appendChild(typingIndicator);
            this.scrollToBottom();
        } else if (!show && typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    scrollToBottom() {
        const messagesContainer = document.getElementById('ai-chat-messages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
    
    clearMessages() {
        const messagesContainer = document.getElementById('ai-chat-messages');
        if (messagesContainer) {
            messagesContainer.innerHTML = '';
        }
    }
    
    async loadConversationHistory() {
        if (!this.conversationId) return;
        
        try {
            const response = await fetch(`${this.apiBase}/conversation/${this.conversationId}`);
            if (!response.ok) return;
            
            const data = await response.json();
            
            if (data.history && Array.isArray(data.history)) {
                data.history.forEach(turn => {
                    this.addMessage(turn.user_message, 'user');
                    this.addMessage(turn.assistant_message, 'bot');
                });
            }
        } catch (error) {
            console.error('Failed to load conversation:', error);
        }
    }
    
    startVoiceInput() {
        if (!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window)) {
            alert('Voice input not supported in your browser. Please use Chrome.');
            return;
        }
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        
        const voiceBtn = document.getElementById('ai-chat-voice-btn');
        const input = document.getElementById('ai-chat-input');
        
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = false;
        
        recognition.onstart = () => {
            if (voiceBtn) {
                voiceBtn.innerHTML = '<i class="fas fa-stop-circle text-danger"></i>';
                voiceBtn.classList.add('recording');
            }
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            if (input) {
                input.value = transcript;
                setTimeout(() => this.sendMessage(), 300);
            }
        };
        
        recognition.onend = () => {
            if (voiceBtn) {
                voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
                voiceBtn.classList.remove('recording');
            }
        };
        
        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (voiceBtn) {
                voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
                voiceBtn.classList.remove('recording');
            }
            alert(`Voice recognition error: ${event.error}`);
        };
        
        recognition.start();
    }
}

// Initialize chat when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('ai-chat-widget')) {
        console.log('✅ Initializing AI Chat widget...');
        window.aiChat = new AIChat('ai-chat-widget', {
            apiBase: '/api/ai'
        });
        console.log('✅ AI Chat initialized successfully');
    }
});

console.log('✅ Chat.js loaded successfully');