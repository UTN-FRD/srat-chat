from flask import Flask, request, jsonify, render_template
import dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langgraph.prebuilt import create_react_agent
from langchain_google_community import GmailToolkit
from langchain_google_community.gmail.utils import build_resource_service, get_gmail_credentials
import os

dotenv.load_dotenv()
app = Flask(__name__)

# llm
llm = ChatGroq(model_name='llama3-70b-8192')

# GmailToolkit
try:
    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=["https://mail.google.com/"],
        client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    toolkit = GmailToolkit(api_resource=api_resource)
except Exception as e:
    print(f"Error GmailToolkit: {str(e)}")
    toolkit = GmailToolkit()

tools = toolkit.get_tools()

#  Historial con formato HTML
def formatear_historial(historial):
    texto = "<div style='font-family: sans-serif; font-size: 14px;'>"
    for msg in historial.messages:
        role = "Usuario" if msg.type == "human" else "Asistente"
        contenido = msg.content.strip().replace("\n", "<br>")
        texto += f"<strong>{role}:</strong><br>{contenido}<br><br>"
    texto += "</div>"
    return texto

# prompt
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
Tu rol es asistir a los profesores de distintas materias de diferentes carreras a usar el sistema de carga de temas. Responde solo preguntas sobre ese sistema.
Los alumnos no utilizan este sistema.

El sistema funciona de dos maneras:
- Con un celular o notebook se accede a la red wifi FRDWLAN (solo en la facultad), esta red la gestiona el GESIN (nosotros no podemos resolverlo).
- Desde las PC que están en el pasillo de los Departamentos de las Carreras (aquí es donde funciona el asistente, o sea, vos)

El sistema funciona así:
- El profesor o auxiliar, ingresa con legajo y contraseña específica para este sistema.
- Se carga el tema del día y se cierra sesión.
- La primera vez que ingresa en el día guarda la hora de ingreso.
- La última vez que ingresa al sistema guarda la hora de egreso.

Problemas comunes que requieren envío de correo para resolverlo:
- Si no puede ingresar:
    - puede ser que se haya olvidado la contraseña o el legajo.
    - puede ser que no esté dado de alta en el sistema como usuario.
- Si no aparece la materia:
    - puede ser que el horario de la materia esté mal cargado.
    - puede ser que el usuario no esté asignado a la materia.

Para cualquiera de estos casos, solicitar nombre, apellido, legajo, materia y carrera para incluir esa información en el correo electrónico.
Ofrecele enviar una copia del correo electrónico, en ese caso vas a necesitar también una dirección de correo del usuario.

---

Cuando no puedas dar una respuesta completa de ayuda debes enviar un correo electrónico utilizando la herramienta send_gmail_message con estos datos:
   - to: ["fabrizio14@live.com.ar"] (si el usuario te proporcionó una dirección de correo electrónico agregarla aqui)
   - subject: "Notificación: Asistente de Carga de Temas - Historial de Conversación"
   - message: envía el historial de la conversación completo.
Luego de enviar el correo termina la convesación avisando que enviaste un correo para que vean el tema.

---

Si solo hizo 1 pregunta irrelevante, responde con algo como:
   "Solo puedo ayudarte con el sistema de carga de temas. ¿Querés que te ayude con eso?"

Nunca respondas temas ajenos al sistema. Usa tus herramientas si es necesario.
"""
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

# Crear agente ReAct
agent_executor = create_react_agent(llm, tools, prompt=prompt)
chat_history = ChatMessageHistory()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    chat_history.add_user_message(user_message)

    # Ejecutar el modelo
    events = agent_executor.stream(
        {"messages": chat_history.messages},
        stream_mode="values"
    )

    response_content = ""
    for event in events:
        print("[DEBUG EVENT]:", event)
        response_content = event["messages"][-1].content
        print("[DEBUG RESPONSE]:", response_content)

    chat_history.add_ai_message(response_content)

   

    return jsonify({"response": response_content})

if __name__ == "__main__":
    app.run(debug=True)
