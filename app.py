from flask import Flask, request, jsonify, render_template
import dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ChatMessageHistory

dotenv.load_dotenv()

app = Flask(__name__)

# Configuración del modelo de lenguaje

model = 'llama3-8b-8192'

groq_chat = ChatGroq(
    model_name=model
)

# Definir el prompt del chatbot
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres un asistente para profesores. Tu trabajo es guiarlos sobre cómo realizar tareas en el sistema, como ingresar su correo electrónico y contraseña, o registrar las horas de entrada y salida. No realices acciones por ellos, solo proporciona instrucciones claras."
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

# Crear una cadena con el prompt y el modelo de chat
chain = prompt | groq_chat

# Crear historial de mensajes para manejar la interacción
chat_history = ChatMessageHistory()

# Cargar respuestas preconfiguradas desde el archivo
def cargar_respuestas_desde_txt(archivo):
    respuestas = {}
    with open(archivo, 'r', encoding='utf-8') as file:
        for linea in file:
            if ':' in linea:
                pregunta, respuesta = linea.strip().split(':', 1)
                respuestas[pregunta.strip()] = respuesta.strip()
    return respuestas

predefined_responses = cargar_respuestas_desde_txt('respuestas.txt')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if user_message in predefined_responses:
        response_content = predefined_responses[user_message]
    else:
        chat_history.add_user_message(user_message)
        response = chain.invoke({"messages": chat_history.messages})
        chat_history.add_ai_message(response)
        response_content = response.content
    return jsonify({"response": response_content})

if __name__ == "__main__":
    app.run(debug=True)
