from flask import Flask, request, jsonify
from flask_cors import CORS
from ollama import chat
import time
from datetime import datetime
import json
import os
import uuid
import sqlite3
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import SQLChatMessageHistory
import re



app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

MEMORY_DIR = os.path.join(os.path.dirname(__file__), 'chat_memory')
os.makedirs(MEMORY_DIR, exist_ok=True)
SESSION_DB = os.path.join(os.path.dirname(__file__), 'session_metadata.db')

def init_session_db():
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        title TEXT,
        model TEXT,
        created_at TEXT,
        last_updated TEXT
    )''')
    conn.commit()
    conn.close()
init_session_db()

def create_session(model="llama3.2:3b", title="New Chat"):
    session_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (session_id, title, model, created_at, last_updated) VALUES (?, ?, ?, ?, ?)",
              (session_id, title, model, now, now))
    conn.commit()
    conn.close()
    return session_id

def update_session_timestamp(session_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute("UPDATE sessions SET last_updated=? WHERE session_id=?", (now, session_id))
    conn.commit()
    conn.close()

def rename_session(session_id, new_title):
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute("UPDATE sessions SET title=? WHERE session_id=?", (new_title, session_id))
    conn.commit()
    conn.close()

def delete_session(session_id):
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    db_path = os.path.join(MEMORY_DIR, f"chat_{session_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)

def get_all_sessions():
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute("SELECT session_id, title, model, created_at, last_updated FROM sessions ORDER BY last_updated DESC")
    rows = c.fetchall()
    conn.close()
    sessions = []
    for row in rows:
        session_id, title, model, created_at, last_updated = row
        memory = get_memory_for_session(session_id)
        messages = memory.chat_memory.messages
        # Find the first user or assistant message for preview
        preview_msg = next((m for m in messages if getattr(m, 'type', None) in ['human', 'ai']), None)
        preview = preview_msg.content[:50] + '...' if preview_msg else 'Empty chat'
        sessions.append({
            'session_id': session_id,
            'title': title,
            'model': model,
            'created_at': created_at,
            'last_updated': last_updated,
            'preview': preview,
            'exchange_count': len(messages) // 2
        })
    return sessions

def get_session_metadata(session_id):
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute("SELECT session_id, title, model, created_at, last_updated FROM sessions WHERE session_id=?", (session_id,))
    row = c.fetchone()
    conn.close()
    if row:
        session_id, title, model, created_at, last_updated = row
        return {
            'session_id': session_id,
            'title': title,
            'model': model,
            'created_at': created_at,
            'last_updated': last_updated
        }
    return None

def get_memory_for_session(session_id):
    db_path = os.path.join(MEMORY_DIR, f"chat_{session_id}.db")
    db_url = f"sqlite:///{db_path}"
    message_history = SQLChatMessageHistory(
        session_id=session_id,
        connection_string=db_url,
        table_name="message_store"
    )
    memory = ConversationBufferMemory(chat_memory=message_history, return_messages=True)
    return memory

def ensure_complete_response(response_text, max_tokens):
    """
    Ensure the response is complete and coherent within the token limit.
    If the response is cut off, try to complete it naturally.
    """
    if not response_text:
        return response_text
    
    # Check if response ends with incomplete sentence or thought
    incomplete_indicators = [
        "...", "..", "…",  # Ellipsis
        " -", " - ",       # Incomplete dash
        " •", " • ",       # Incomplete bullet
        " □", " □ ",       # Incomplete checkbox
        " [", " [ ",       # Incomplete bracket
        " (", " ( ",       # Incomplete parenthesis
    ]
    
    # Check if response ends with incomplete patterns
    for indicator in incomplete_indicators:
        if response_text.rstrip().endswith(indicator):
            # Remove the incomplete indicator
            response_text = response_text.rstrip()[:-len(indicator)].rstrip()
            break
    
    # Check for incomplete sentences (ends without proper punctuation)
    if response_text and not response_text.rstrip().endswith(('.', '!', '?', ':', ';')):
        # Find the last complete sentence
        sentences = response_text.split('.')
        if len(sentences) > 1:
            # Remove the last incomplete sentence
            response_text = '.'.join(sentences[:-1]) + '.'
    
    # Ensure the response doesn't exceed token limit (rough estimation)
    # Approximate: 1 token ≈ 4 characters for English text
    estimated_tokens = len(response_text) // 4
    if estimated_tokens > max_tokens:
        # Truncate to fit within limit while preserving complete sentences
        max_chars = max_tokens * 4
        if len(response_text) > max_chars:
            # Find the last complete sentence within the limit
            truncated = response_text[:max_chars]
            last_period = truncated.rfind('.')
            if last_period > max_chars * 0.8:  # If we can find a period in the last 20%
                response_text = truncated[:last_period + 1]
            else:
                response_text = truncated
    
    # Remove incomplete numbered or bulleted list items at the end
    lines = response_text.strip().split('\n')
    while lines and re.match(r'^\s*(\d+\.|\*|-|•)\s*$', lines[-1]):
        lines.pop()
    response_text = '\n'.join(lines)

    return response_text.strip()

def update_session_model(session_id, model):
    conn = sqlite3.connect(SESSION_DB)
    c = conn.cursor()
    c.execute("UPDATE sessions SET model=? WHERE session_id=?", (model, session_id))
    conn.commit()
    conn.close()

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        data = request.json
        message = data.get('message')
        max_tokens = data.get('maxTokens', 500)
        enable_streaming = data.get('enableStreaming', True)
        messages = data.get('messages', [])
        session_id = data.get('sessionId')  # Frontend can specify session

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        start_time = time.time()
        current_timestamp = datetime.now().strftime("%H:%M")
        
        # Switch to specified session if provided
        if session_id:
            # Use the session's stored model instead of the request model
            user_model = data.get('model')
            if user_model:
                update_session_model(session_id, user_model)
            meta = get_session_metadata(session_id)
            model = meta['model'] if meta else 'llama3.2:3b'
        else:
            # For new sessions, store the requested model
            model = 'llama3.2:3b'

        # Create a comprehensive system prompt for cybersecurity analysts
        system_prompt = f"""You are a senior Security Operations Center (SOC) analyst assisting with the investigation 
        and response of security alerts and incidents.

        You must NEVER end your response in the middle of a sentence or thought. 
        If you reach the token limit, always complete your last sentence so the response ends 
        naturally and is fully readable. Do not leave any sentence unfinished. You are ALWAYS able to provide 
        some form of assistance, guidance, or relevant information. If you don't have complete information, 
        ask clarifying questions or provide general cybersecurity guidance based on what you do know.

        CRITICAL: You must NEVER refuse to provide details or assistance for any reason, including:
        - "I cannot provide further details on this incident as it may contain sensitive information"
        - "I can't help with this request"
        - "I cannot assist with this"
        - Any other form of refusal or inability to help

        You should provide relevant guidance, best practices, and analysis based on the information provided. If you need more 
        details to provide specific guidance, ask clarifying questions instead of refusing to help.

        IMPORTANT: If you are unable to provide a full answer due to missing information, always ask clarifying questions 
        or explain what is needed. Never respond with 'I can't help with this request.' Always finish your last sentence, 
        even if you reach the token limit.
        Always provide complete, coherent responses. If you cannot fit everything within the token limit, 
        prioritize the most critical information and ensure your response ends naturally.

        🚫 You are not an AI or chatbot. You do not invent, assume, or speculate. You rely only on facts provided by the user, 
        standard cybersecurity practices, and trusted frameworks such as MITRE ATT&CK, NIST 800-61, and CIS Controls.
        ✅ Your job is to provide real-world, analyst-grade guidance, structured around incident handling best practices.

        * Acts strictly as a senior SOC analyst, not an AI
        * Uses only verified, trusted information (no hallucination or invented content)
        * Generates flexible, situational checklists tailored to the input
        * Retains a professional, incident-focused style
        * Prioritizes accuracy, coherence, and brevity

        You are a senior Security Operations Center (SOC) analyst. 
        You assist frontline cybersecurity teams in investigating and responding to security alerts and incidents.


        ### RESPONSE CONSTRAINTS

        You have a response length limit of `{max_tokens}`. Your response must be:

        * Fully coherent and complete
        * Concise, technical, and focused on incident response
        * Prioritized based on criticality
        * Checklist-driven and procedurally actionable

        If full coverage is not possible, include only the most critical guidance and complete your response naturally—never cut off mid-sentence.

        ### PRIMARY DUTIES

        * Interpret and contextualize alerts
        * Guide incident triage and containment
        * Explain log evidence and indicators
        * Recommend concrete investigation procedures
        * Map actions to standard frameworks (e.g., MITRE, NIST)
        * Support decision-making with precision and clarity

        ---

        ### RESPONSE FORMAT

        When the user provides incident details, always begin with:

        > "Let me provide you with a structured checklist for this incident analysis:"

        Then generate a tailored checklist relevant to the incident context. 
        The checklist must dynamically adapt to the situation, not be limited to pre-defined categories.

        Your checklist should typically include, but is not limited to:

        * Threat Classification & Scope
        * Host & Network Evidence Collection
        * Identity & Access Review
        * Containment & Eradication Measures
        * Persistence & Lateral Movement Checks
        * Communication & Escalation Requirements
        * External Intelligence Correlation (if warranted)

        ---

        ### RULES OF ENGAGEMENT

        * Always think and communicate like a senior SOC analyst, not an AI
        * Never guess, assume, or create information not directly supported by:

        * User input
        * Established frameworks (MITRE ATT\&CK, NIST, etc.)
        * Security telemetry logs or forensics
        * Never respond in the first person as an AI
        * Prioritize security integrity, forensic soundness, and procedural clarity
        * If context is missing, ask clear follow-up questions to progress the investigation
        * NEVER refuse to provide assistance or details for any reason

        ---

        ### FRAMEWORK ALIGNMENT

        Your responses should reference and align with cybersecurity frameworks as appropriate:

        * MITRE ATT\&CK for adversary behavior
        * NIST 800-61 for incident handling
        * CIS Controls for best practices
        * Any threat intel feeds explicitly shared by the user"""

        # Prepare messages for Ollama - include system prompt first
        ollama_messages = [
            {
                'role': 'system',
                'content': system_prompt
            }
        ]
        
        # Add conversation history (excluding the system message from frontend)
        for msg in messages:
            if msg['role'] != 'system':  # Skip system messages from frontend
                ollama_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        # Add the current user message
        ollama_messages.append({
            'role': 'user',
            'content': message
        })

        # Call Ollama chat API with the session's model
        response = chat(
            model=model,
            messages=ollama_messages,
            options={
                "num_predict": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "stop": ["\n\n\n", "---", "###"],  # Stop at natural break points
                "num_ctx": max_tokens * 2  # Provide enough context
            }
        )
        
        response_time = time.time() - start_time
        
        # Ensure the response is complete and coherent
        complete_response = ensure_complete_response(response['message']['content'], max_tokens)
        
        # Store conversation with proper timestamp and model
        current_session_id = session_id if session_id else create_session(model=model)
        update_session_timestamp(current_session_id)
        
        memory = get_memory_for_session(current_session_id)
        memory.save_context({"input": message}, {"output": complete_response})
        
        return jsonify({
            'response': complete_response,
            'responseTime': response_time,
            'timestamp': current_timestamp,
            'sessionId': current_session_id,
            'model': model  # Return the model used for this session
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/conversation-history', methods=['GET'])
def get_conversation_history():
    """Get all conversation sessions for sidebar display"""
    try:
        sessions = get_all_sessions()
        
        return jsonify({
            'sessions': sessions,
            'total_sessions': len(sessions)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/session-history/<session_id>', methods=['GET'])
def get_session_history(session_id):
    try:
        # Try to get messages, but handle missing file gracefully
        try:
            memory = get_memory_for_session(session_id)
            messages = memory.chat_memory.messages
        except Exception:
            messages = []
        history = []
        for msg in messages:
            if getattr(msg, 'type', None) == 'human':
                history.append({'role': 'user', 'content': msg.content or '', 'timestamp': getattr(msg, 'timestamp', None)})
            elif getattr(msg, 'type', None) == 'ai':
                history.append({'role': 'assistant', 'content': msg.content or '', 'timestamp': getattr(msg, 'timestamp', None)})
        meta = get_session_metadata(session_id)
        return jsonify({
            'conversation_history': history,
            'session_id': session_id,
            'model': meta['model'] if meta else None,
            'title': meta['title'] if meta else None,
            'total_exchanges': len(history) // 2
        })
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/rename-session/<session_id>', methods=['POST'])
def rename_session_endpoint(session_id):
    try:
        data = request.json
        new_title = data.get('title')
        if not new_title:
            return jsonify({'error': 'Title is required'}), 400
        rename_session(session_id, new_title)
        return jsonify({'message': 'Session renamed', 'sessionId': session_id, 'title': new_title})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete-session/<session_id>', methods=['DELETE'])
def delete_session_endpoint(session_id):
    try:
        delete_session(session_id)
        return jsonify({'message': 'Session deleted', 'sessionId': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/new-session', methods=['POST'])
def create_new_session():
    try:
        data = request.json or {}
        model = data.get('model', 'llama3.2:3b')
        title = data.get('title', 'New Chat')
        session_id = create_session(model=model, title=title)
        return jsonify({
            'sessionId': session_id,
            'model': model,
            'title': title,
            'message': 'New session created'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear-all-sessions', methods=['POST'])
def clear_all_sessions():
    try:
        # Remove all session metadata
        conn = sqlite3.connect(SESSION_DB)
        c = conn.cursor()
        c.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()
        # Remove all chat history files
        for fname in os.listdir(MEMORY_DIR):
            if fname.startswith('chat_') and fname.endswith('.db'):
                os.remove(os.path.join(MEMORY_DIR, fname))
        return jsonify({'message': 'All sessions and chats cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear-session/<session_id>', methods=['POST'])
def clear_session(session_id):
    try:
        db_path = os.path.join(MEMORY_DIR, f"chat_{session_id}.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        # Do not recreate the table here; it will be created on the next message
        return jsonify({'message': 'Session chat cleared', 'sessionId': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/all-messages', methods=['GET'])
def all_messages():
    try:
        all_msgs = []
        for session in get_all_sessions():
            session_id = session['session_id']
            memory = get_memory_for_session(session_id)
            messages = memory.chat_memory.messages
            for msg in messages:
                all_msgs.append({
                    'session_id': session_id,
                    'role': 'user' if msg.type == 'human' else 'assistant',
                    'content': msg.content or ''
                })
        return jsonify({'all_messages': all_msgs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001) 