import streamlit as st
import httpx
import json
import io
import os
from datetime import date

st.set_page_config(page_title="Voice-NLP Tester", page_icon="🎙️", layout="wide")

st.title("🎙️ Voice-NLP Tester")
st.markdown("Testez toutes les fonctionnalités de votre service Voice-NLP (ASR, TTS, NLP Extraction, Dialogue).")

# Configuration
default_url = os.getenv("API_BASE_URL", "http://localhost:8100")
API_BASE_URL = st.sidebar.text_input("API Base URL", value=default_url)
TIMEOUT = st.sidebar.slider("Timeout (seconds)", 10, 300, 120)

if "history" not in st.session_state:
    st.session_state.history = []

def add_to_history(endpoint, input_data, response):
    st.session_state.history.append({
        "time": date.today().isoformat(),
        "endpoint": endpoint,
        "input": input_data,
        "response": response
    })

tabs = st.tabs(["Transcription (ASR)", "Synthèse (TTS)", "Extraction (NLP)", "Pipeline (Voice-to-JSON)", "Dialogue", "Historique"])

# --- TAB 1: Transcription ---
with tabs[0]:
    st.header("Transcription (Whisper)")
    audio_file = st.file_uploader("Upload an audio file", type=["wav", "mp3", "m4a"], key="asr_upload")
    audio_record = st.audio_input("Ou enregistrez directement", key="asr_record")
    
    input_audio = audio_record if audio_record else audio_file

    if input_audio:
        st.audio(input_audio)
        if st.button("Transcréer", key="btn_asr"):
            with st.spinner("Transcription en cours..."):
                try:
                    raw_audio = input_audio.read()
                    files = {"audio": (input_audio.name or "audio.wav", raw_audio, "audio/wav")}
                    r = httpx.post(f"{API_BASE_URL}/v1/transcribe", files=files, timeout=TIMEOUT)
                    add_to_history("ASR", "audio file", r.json() if r.status_code == 200 else r.text)
                    if r.status_code == 200:
                        res = r.json()
                        st.success(f"**Texte:** {res['text']}")
                        st.info(f"**Langue détectée:** {res['language']} (Confiance: {res['confidence']:.2f})")
                    else:
                        st.error(f"Erreur {r.status_code}: {r.text}")
                except Exception as e:
                    st.error(f"Erreur de connexion: {e}")

# --- TAB 2: TTS ---
with tabs[1]:
    st.header("Synthèse Vocale (Kokoro)")
    text_to_speak = st.text_area("Texte à synthétiser", value="Bonjour, comment puis-je vous aider aujourd'hui ?")
    lang_tts = st.selectbox("Langue", options=["fr", "en", "wo"], index=0)
    
    if st.button("Générer l'audio", key="btn_tts"):
        if text_to_speak:
            with st.spinner("Génération..."):
                try:
                    data = {"text": text_to_speak, "language": lang_tts}
                    r = httpx.post(f"{API_BASE_URL}/v1/tts", data=data, timeout=TIMEOUT)
                    add_to_history("TTS", data, "Audio content" if r.status_code == 200 else r.text)
                    if r.status_code == 200:
                        st.audio(r.content, format="audio/wav")
                    else:
                        st.error(f"Erreur {r.status_code}: {r.text}")
                except Exception as e:
                    st.error(f"Erreur de connexion: {e}")

# --- TAB 3: Extraction ---
with tabs[2]:
    st.header("Extraction d'Intentions (Ollama)")
    col1, col2 = st.columns(2)
    
    with col1:
        text_input = st.text_area("Texte d'entrée", value="Je veux aller à Dakar demain matin avec 2 amis.")
        today_val = st.date_input("Date 'Aujourd'hui'", value=date.today())
    
    with col2:
        default_schema = {
            "context": "Transport au Sénégal",
            "fields": [
                {"name": "destination", "type": "string", "description": "Ville d'arrivée", "required": True},
                {"name": "passengers", "type": "integer", "description": "Nombre de personnes", "required": False},
                {"name": "date", "type": "date", "description": "Date du trajet", "required": False}
            ]
        }
        schema_input = st.text_area("Schéma JSON", value=json.dumps(default_schema, indent=2), height=300)

    if st.button("Extraire", key="btn_extract"):
        with st.spinner("Analyse NLP..."):
            try:
                payload = {
                    "text": text_input,
                    "schema": json.loads(schema_input),
                    "today": today_val.isoformat()
                }
                r = httpx.post(f"{API_BASE_URL}/v1/extract", json=payload, timeout=TIMEOUT)
                add_to_history("NLP", payload, r.json() if r.status_code == 200 else r.text)
                if r.status_code == 200:
                    st.json(r.json())
                else:
                    st.error(f"Erreur {r.status_code}: {r.text}")
            except Exception as e:
                st.error(f"Erreur: {e}")

# --- TAB 4: Pipeline ---
with tabs[3]:
    st.header("Voice to JSON (Pipeline)")
    col_a, col_b = st.columns(2)
    
    with col_a:
        p_audio_file = st.file_uploader("Upload audio", type=["wav", "mp3"], key="p_upload")
        p_audio_record = st.audio_input("Record audio", key="p_record")
        p_input = p_audio_record if p_audio_record else p_audio_file
        
    with col_b:
        p_schema_input = st.text_area("Schéma JSON", value=json.dumps(default_schema, indent=2), height=250, key="p_schema")

    if st.button("Lancer le Pipeline", key="btn_pipeline"):
        if p_input:
            with st.spinner("Transcription + Extraction..."):
                try:
                    files = {"audio": (p_input.name or "audio.wav", p_input.read(), "audio/wav")}
                    data = {"schema": p_schema_input}
                    r = httpx.post(f"{API_BASE_URL}/v1/voice-to-json", files=files, data=data, timeout=TIMEOUT)
                    add_to_history("Pipeline", data, r.json() if r.status_code == 200 else r.text)
                    if r.status_code == 200:
                        st.json(r.json())
                    else:
                        st.error(f"Erreur {r.status_code}: {r.text}")
                except Exception as e:
                    st.error(f"Erreur: {e}")

# --- TAB 5: Dialogue ---
with tabs[4]:
    st.header("Dialogue Interactif (Slot-filling)")
    
    if "dialogue_state" not in st.session_state:
        st.session_state.dialogue_state = {}
    
    if st.button("Réinitialiser le dialogue"):
        st.session_state.dialogue_state = {}
        st.rerun()

    st.write("**Champs collectés :**", st.session_state.dialogue_state)
    
    d_audio = st.audio_input("Répondez par la voix", key="d_record")
    d_text = st.text_input("Ou par texte")
    
    if st.button("Envoyer", key="btn_dialogue"):
        input_data = {}
        files = None
        
        if d_audio:
            files = {"audio": ("input.wav", d_audio.read(), "audio/wav")}
        elif d_text:
            input_data["text"] = d_text
            
        if files or d_text:
            with st.spinner("Traitement..."):
                try:
                    data = {
                        "collected": json.dumps(st.session_state.dialogue_state),
                        "ask_optional": "true"
                    }
                    if d_text: data["text"] = d_text
                    
                    r = httpx.post(f"{API_BASE_URL}/v1/dialogue-audio", files=files, data=data, timeout=TIMEOUT)
                    
                    if r.status_code == 200:
                        state_json = r.headers.get("X-Dialogue-State")
                        if state_json:
                            state = json.loads(state_json)
                            st.session_state.dialogue_state = state["collected"]
                            add_to_history("Dialogue", data, state)
                            
                            st.markdown(f"**Transcription:** {state['transcription']}")
                            st.markdown(f"**Question suivante:** {state['next_question']}")
                            if state["is_complete"]:
                                st.success("Dialogue terminé !")
                            
                            st.audio(r.content, format="audio/wav")
                        else:
                            st.error("Header X-Dialogue-State manquant")
                    else:
                        st.error(f"Erreur {r.status_code}: {r.text}")
                except Exception as e:
                    st.error(f"Erreur: {e}")

# --- TAB 6: Historique ---
with tabs[5]:
    st.header("Historique des échanges")
    if not st.session_state.history:
        st.info("Aucun échange pour le moment.")
    else:
        for i, entry in enumerate(reversed(st.session_state.history)):
            with st.expander(f"{entry['time']} - {entry['endpoint']}"):
                st.write("**Entrée :**")
                st.json(entry['input'])
                st.write("**Réponse :**")
                st.json(entry['response'])
