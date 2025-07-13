import streamlit as st
from ollama import chat
import time

# Model options - you can switch between these
MODELS = {
    'Fast (3B)': 'llama3.2:3b',  # Much faster, good for general chat
    'Balanced (8B)': 'deepseek-r1:8b',  # Your current model
    'Fast (1B)': 'llama3.2:1b',  # Fastest option, smaller context
}

# Default to the fastest model
DEFAULT_MODEL = 'Fast (3B)'

st.set_page_config(page_title="Chatbot", page_icon="🤖")
st.title("🤖 Chatbot")

# Model selection in sidebar
st.sidebar.header("Settings")
selected_model = st.sidebar.selectbox(
    "Choose Model:",
    list(MODELS.keys()),
    index=list(MODELS.keys()).index(DEFAULT_MODEL)
)

# Performance settings
enable_streaming = st.sidebar.checkbox("Enable Streaming", value=True, help="Shows response as it's being generated")
max_tokens = st.sidebar.slider("Max Response Length", 100, 1000, 500, help="Limit response length for faster replies")

# Initialize session state for chat history
if 'messages' not in st.session_state:
    st.session_state['messages'] = [
        {"role": "system", "content": """You are an AI assistant designed to help 
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
        Keep responses concise and to the point."""}
    ]

# Clear chat button
if st.sidebar.button("Clear Chat"):
    st.session_state['messages'] = [st.session_state['messages'][0]]  # Keep system message
    st.rerun()

# Display chat history
for msg in st.session_state['messages']:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    elif msg["role"] == "assistant":
        st.chat_message("assistant").markdown(msg["content"])

# User input box
if prompt := st.chat_input("Type your message and press Enter..."):
    # Add user message to history
    st.session_state['messages'].append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)

    # Show loading indicator
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤔 Thinking...")
        
        # Initialize answer variable
        answer = ""
        
        # Call Ollama chat API with optimizations
        try:
            start_time = time.time()
            
            # Prepare messages with token limit
            messages = st.session_state['messages'][-10:]  # Keep only last 10 messages for context
            
            response = chat(
                model=MODELS[selected_model], 
                messages=messages,
                options={
                    "num_predict": max_tokens,  # Limit response length
                    "temperature": 0.7,  # Slightly lower for faster, more focused responses
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            )
            
            answer = response.message.content
            response_time = time.time() - start_time
            
            # Display response with timing info
            message_placeholder.markdown(f"{answer}\n\n*Response time: {response_time:.2f}s*")
            
        except Exception as e:
            error_msg = f"❌ Error: {e}"
            answer = error_msg
            message_placeholder.markdown(error_msg)

    # Add assistant message to history
    st.session_state['messages'].append({"role": "assistant", "content": answer})

# Performance tips in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("**Performance Tips:**")
st.sidebar.markdown("• Use smaller models (1B/3B) for faster responses")
st.sidebar.markdown("• Reduce max response length")
st.sidebar.markdown("• Clear chat history periodically")
st.sidebar.markdown("• Keep messages concise")
