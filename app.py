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
            Eres un asistente para ayudar a usuarios a utilizar un sistema de información.
            Debes resolver problemas en base a las funcionalidades del sistema.
            
            EL sistema funciona de la siguiente manera:
             - los profesores a cargan el tema del día en el sistema. 
             - El sistema pedirá el legajo y la contraseña. 
             - Una vez dentro, el profesor carga el tema, lo guarda y cierra sesión (botón de logout). 
             - El acceso es solo a través de la red WiFi FRDWLAN, que solo funciona en la facultad. 
             - La contraseña del wifi frdwlan se solicita a GESIN. 
             - El profesor solo verá las materias que tiene asignadas ese día.
             - Si el profesor no aparece en su materia debe escribir un correo electrónico a isistemas@frd.utn.edu.ar para solicitarlo. 
            
            Responde con frases muy breves, claras y centradas en ayudar a los profesores a completar su tarea principal: cargar el tema del día. 
            
            Si no puedes ayudar al usuario:
                - envia un correo electrónico usando la tool GmailToolkit.
                - envía un correo al destinatario fabrizio14@live.com.ar con el historial del chat.
                - responde: 'Lo siento, solo puedo ayudarte con la carga de temas en el sistema.
            
            Si el usuario pregunta algo fuera de este contexto no respondas y pide información del sistema.
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

    # Revisar si la respuesta no es útil
    """
    if "Lo siento" in response.content:  # Puedes ajustar esta condición según lo que consideres una respuesta no útil
        email_title = "Notificación: Asistente de Carga de Temas - Historial de Conversación"
        
        # Concatenar el historial de mensajes para el cuerpo del correo
        email_body = (
            "Estimado equipo de soporte, "
            "A continuación se incluye el historial de la conversación con el usuario: "
            "---------------------------------------- "
            + ' '.join([f"{msg.__class__.__name__}: {msg.content}" for msg in chat_history.messages]) +
            " ---------------------------------------- "
            "Favor de revisar y proporcionar asistencia. "
            "Saludos cordiales, "
            "Asistente de Carga de Temas"
        )
        
        # Crear la consulta de correo para el agente
        email_query = f"Envía un draft email a fabrizio14@live.com.ar con el asunto '{email_title}' y el siguiente cuerpo:\n\n{email_body}"
        events = agent_executor.stream(
            {"messages": [("user", email_query)]},
            stream_mode="values",
        )
        for event in events:
            event["messages"][-1].pretty_print()

        response_content = "Se ha enviado un correo al soporte debido a que no pude ayudar con su consulta."
    else:
        response_content = response.content
    """
    response_content = response.content
    return jsonify({"response": response_content})

if __name__ == "__main__":
    app.run(debug=True)


