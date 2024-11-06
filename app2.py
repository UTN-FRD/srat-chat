from flask import Flask, request, jsonify, render_template
import dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langgraph.prebuilt import create_react_agent
from langchain_google_community import GmailToolkit
import os

dotenv.load_dotenv()

app = Flask(__name__)

# Configuración del modelo de lenguaje
model = 'llama3-8b-8192'
llm = ChatGroq(model_name=model)

# Configuración del GmailToolkit
toolkit = GmailToolkit()
tools = toolkit.get_tools()

# Crear el agente ReAct que usará el toolkit de Gmail
agent_executor = create_react_agent(llm, tools)

# Definir el prompt del chatbot con las instrucciones de envío de correos
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            Eres un asistente simple para ayudar a los profesores a cargar el tema del día en su sistema. 
            El sistema pedirá el legajo y la contraseña. 
            Una vez dentro, el profesor carga el tema, lo guarda y cierra sesión (botón de logout). 
            El acceso es solo a través de la red WiFi FRDWLAN, que solo funciona en la facultad. La contraseña se obtiene con GESIN. 
            Si no aparece una materia y nunca se ha enviado un correo, debe escribirse a isistemas@frd.utn.edu.ar para asignarla. 
            Responde con frases muy breves, claras y centradas en ayudar a los profesores a completar su tarea principal: cargar el tema del día. 
            El profesor solo verá las materias que tiene asignadas ese día.
            Si el usuario pregunta algo fuera de este contexto, responde: 'Lo siento, solo puedo ayudarte con la carga de temas en el sistema.'
            
            Si no puedes ayudar al usuario, envía un correo automáticamente a fabrizio14@live.com.ar con el historial del chat.
            """
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

# Crear la cadena con el prompt y el modelo de chat
chain = prompt | llm
chat_history = ChatMessageHistory()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    
    # Agregar mensaje del usuario al historial
    chat_history.add_user_message(user_message)
    
    # Obtener respuesta del modelo
    response = chain.invoke({"messages": chat_history.messages})

    # Crear la consulta de correo para el agente si no puede ayudar al usuario
    email_query = (
        "Si no puedes ayudar al usuario, envía un correo automáticamente a fabrizio14@live.com.ar con el historial del chat. "
        "El asunto del correo debe ser 'Notificación: Asistente de Carga de Temas - Historial de Conversación'. "
        "El cuerpo del correo debe incluir el historial de la conversación y una solicitud de asistencia. "
        "Aquí está el historial de la conversación hasta ahora:"
        "----------------------------------------"
         ''.join([f'{msg.sender}: {msg.content}' for msg in chat_history.messages]) +
        "----------------------------------------"
        "Favor de revisar y proporcionar asistencia."
        "Saludos cordiales,"
        "Asistente de Carga de Temas"
    )

    # Ejecutar el agente con la consulta de correo
    events = agent_executor.stream(
        {"messages": [("user", email_query)]},
        stream_mode="values",
    )
    for event in events:
        event["messages"][-1].pretty_print()

    response_content = response.content

    return jsonify({"response": response_content})

if __name__ == "__main__":
    app.run(debug=True)