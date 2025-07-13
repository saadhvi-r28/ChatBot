# 🤖 ChatBot - React Frontend

A modern React-based chat interface for interacting with AI models through Ollama, specifically designed for cybersecurity analysts.

## Features

- **Modern React UI**: Clean, responsive interface with real-time chat
- **Model Selection**: Choose between different AI models (1B, 3B, 8B)
- **Performance Settings**: Adjust response length and streaming options
- **Real-time Chat**: Instant message exchange with loading indicators
- **Mobile Responsive**: Works on desktop and mobile devices
- **Error Handling**: Graceful error handling and user feedback

## Prerequisites

- Node.js (v16 or higher)
- Python (v3.8 or higher)
- Ollama installed and running locally

## Installation

### 1. Install Node.js Dependencies

```bash
npm install
```

### 2. Install Python Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Download AI Models (if not already done)

```bash
python download_models.py
```

## Running the Application

### 1. Start the Backend Server

In one terminal:

```bash
cd backend
python app.py
```

The backend will start on `http://localhost:5000`

### 2. Start the React Frontend

In another terminal:

```bash
npm start
```

The React app will start on `http://localhost:3000`

## Usage

1. **Choose Model**: Select from the sidebar which AI model to use
   - Fast (1B): Fastest responses, smaller context
   - Fast (3B): Good balance of speed and quality
   - Balanced (8B): Best quality, slower responses

2. **Adjust Settings**:
   - Enable/disable streaming
   - Set maximum response length (100-1000 tokens)
   - Clear chat history when needed

3. **Start Chatting**: Type your message and press Enter or click Send

## Project Structure

```
ChatBot/
├── public/                 # Static files
├── src/                   # React source code
│   ├── App.js            # Main React component
│   ├── index.js          # React entry point
│   └── index.css         # Styles
├── backend/              # Flask backend
│   ├── app.py           # API server
│   └── requirements.txt # Python dependencies
├── package.json         # Node.js dependencies
└── README.md           # This file
```

## API Endpoints

- `POST /chat`: Send a message and get AI response
- `GET /health`: Health check endpoint

## Performance Tips

- Use smaller models (1B/3B) for faster responses
- Reduce max response length for quicker replies
- Clear chat history periodically to free memory
- Keep messages concise for better performance

## Troubleshooting

### Backend Issues
- Ensure Ollama is running: `ollama serve`
- Check if models are downloaded: `ollama list`
- Verify Python dependencies are installed

### Frontend Issues
- Clear browser cache if UI doesn't update
- Check browser console for JavaScript errors
- Ensure backend is running on port 5000

### CORS Issues
- Backend has CORS enabled for localhost:3000
- If using different ports, update CORS settings in `backend/app.py`

## Development

### Adding New Models
1. Update the `MODELS` object in `src/App.js`
2. Ensure the model is available in Ollama

### Styling Changes
- Modify `src/index.css` for UI updates
- The app uses modern CSS with flexbox and CSS Grid

### Backend Modifications
- Add new endpoints in `backend/app.py`
- Update requirements.txt for new Python packages

## License

This project is open source and available under the MIT License.
