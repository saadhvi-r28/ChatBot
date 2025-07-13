#from langchain_community.chat_message_histories import SQLiteChatMessageHistory
from langchain_community.chat_message_histories import *
print(dir())

history = SQLChatMessageHistory(database_path="test_chat.db", session_id="session_1")
print("It works!")


