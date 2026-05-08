import streamlit as st
import httpx
import json
import os
from datetime import datetime, date

st.set_page_config(page_title="Voice-NLP Tester", page_icon="🎙️", layout="wide")

# --- Config ---
default_url = os.getenv("API_BASE_URL", "http://localhost:8100")
API_BASE_URL = st.sidebar.text_input("API Base URL", value=default_url)
TIMEOUT = st.sidebar.slider("Timeout (seconds)", 10, 300, 120)

# Health check
with st.sidebar:
    st.divider()
    if st.button("Vérifier la connexion"):
        try:
            r = httpx.get(f"{API_BASE_URL}/health", timeout=5)
            if r.status_code == 200:
                st.success("Service en ligne")
            else:
                st.warning(f"Status {r.status_code}")
        except Exception:
            st.error("Service inaccessible")

# --- State ---
if "history" not in st.session_state:
    st.session_state.history = []
if "dialogue_state" not in st.session_state:
    st.session_state.dialogue_state = {}

DEFAULT_SCHEMA = {
    "context": "Transport au Sénégal",
    "fields": [
        {
            "name": "destination",
            "type": "string",
            "description": "Ville d'arrivée",
            "required": True,
        },
        {
            "name": "passengers",
            "type": "integer",
            "description": "Nombre de personnes",
            "required": True,
            "synonyms": ["tickets", "billets", "places", "voyageurs"],
        },
        {
            "name": "date",
            "type": "date",
            "description": "Date du trajet",
            "required": False,
        },
    ],
}


def add_to_history(endpoint, input_data, response):
    st.session_state.history.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "endpoint": endpoint,
        "input": input_data,
        "response": response,
    })


def parse_schema(raw: str):
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, str(e)


def render_extraction_result(res: dict):
    extracted = res.get("extracted", {})
    missing = res.get("missing_fields", [])
    confidence = res.get("confidence", 0)

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown("**Champs extraits**")
        for k, v in extracted.items():
            if k in missing:
                st.error(f"`{k}` → manquant")
            elif v is None:
                st.warning(f"`{k}` → null")
            else:
                st.success(f"`{k}` → **{v}**")
    with col_b:
        st.metric("Confiance", f"{confidence:.0%}")
        if missing:
            st.error(f"Manquants : {', '.join(missing)}")
        else:
            st.success("Tous les champs requis présents")


# --- Title ---
st.title("🎙️ Voice-NLP Tester")

tabs = st.tabs(["Transcription (ASR)", "Synthèse (TTS)", "Extraction (NLP)", "Pipeline (Voice-to-JSON)", "Dialogue", "Historique"])

# --- TAB 1: ASR ---
with tabs[0]:
    st.header("Transcription (Whisper)")
    audio_file = st.file_uploader("Upload un fichier audio", type=["wav", "mp3", "m4a"], key="asr_upload")
    audio_record = st.audio_input("Ou enregistrez directement", key="asr_record")
    input_audio = audio_record if audio_record else audio_file

    if input_audio:
        st.audio(input_audio)
        if st.button("Transcrire", key="btn_asr"):
            with st.spinner("Transcription en cours..."):
                try:
                    raw_audio = input_audio.read()
                    files = {"audio": (getattr(input_audio, "name", None) or "audio.wav", raw_audio, "audio/wav")}
                    r = httpx.post(f"{API_BASE_URL}/v1/transcribe", files=files, timeout=TIMEOUT)
                    result = r.json() if r.status_code == 200 else r.text
                    add_to_history("ASR", "audio file", result)
                    if r.status_code == 200:
                        st.success(f"**Texte :** {result['text']}")
                        st.info(f"**Langue :** {result['language']} — Confiance : {result['confidence']:.2f}")
                    else:
                        st.error(f"Erreur {r.status_code} : {r.text}")
                except Exception as e:
                    st.error(f"Erreur de connexion : {e}")

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
                        st.error(f"Erreur {r.status_code} : {r.text}")
                except Exception as e:
                    st.error(f"Erreur de connexion : {e}")

# --- TAB 3: Extraction ---
with tabs[2]:
    st.header("Extraction d'Intentions (Ollama)")
    col1, col2 = st.columns(2)

    with col1:
        text_input = st.text_area("Texte d'entrée", value="Je veux 2 tickets pour aller à Dakar demain matin.")
        today_val = st.date_input("Date « aujourd'hui »", value=date.today())

    with col2:
        schema_input = st.text_area(
            "Schéma JSON",
            value=json.dumps(DEFAULT_SCHEMA, indent=2, ensure_ascii=False),
            height=320,
        )
        schema_obj, schema_err = parse_schema(schema_input)
        if schema_err:
            st.error(f"JSON invalide : {schema_err}")

    if st.button("Extraire", key="btn_extract", disabled=schema_obj is None):
        with st.spinner("Analyse NLP..."):
            try:
                payload = {"text": text_input, "schema": schema_obj, "today": today_val.isoformat()}
                r = httpx.post(f"{API_BASE_URL}/v1/extract", json=payload, timeout=TIMEOUT)
                result = r.json() if r.status_code == 200 else r.text
                add_to_history("NLP", payload, result)
                if r.status_code == 200:
                    render_extraction_result(result)
                    with st.expander("JSON brut"):
                        st.json(result)
                else:
                    st.error(f"Erreur {r.status_code} : {r.text}")
            except Exception as e:
                st.error(f"Erreur : {e}")

# --- TAB 4: Pipeline ---
with tabs[3]:
    st.header("Voice to JSON (Pipeline)")
    col_a, col_b = st.columns(2)

    with col_a:
        p_audio_file = st.file_uploader("Upload audio", type=["wav", "mp3"], key="p_upload")
        p_audio_record = st.audio_input("Enregistrer", key="p_record")
        p_input = p_audio_record if p_audio_record else p_audio_file

    with col_b:
        p_schema_input = st.text_area(
            "Schéma JSON",
            value=json.dumps(DEFAULT_SCHEMA, indent=2, ensure_ascii=False),
            height=280,
            key="p_schema",
        )
        p_schema_obj, p_schema_err = parse_schema(p_schema_input)
        if p_schema_err:
            st.error(f"JSON invalide : {p_schema_err}")

    if st.button("Lancer le Pipeline", key="btn_pipeline", disabled=p_schema_obj is None):
        if p_input:
            with st.spinner("Transcription + Extraction..."):
                try:
                    files = {"audio": (getattr(p_input, "name", None) or "audio.wav", p_input.read(), "audio/wav")}
                    data = {"schema": p_schema_input}
                    r = httpx.post(f"{API_BASE_URL}/v1/voice-to-json", files=files, data=data, timeout=TIMEOUT)
                    result = r.json() if r.status_code == 200 else r.text
                    add_to_history("Pipeline", data, result)
                    if r.status_code == 200:
                        st.markdown(f"**Transcription :** {result.get('transcription', {}).get('text', '—')}")
                        render_extraction_result(result.get("extraction", result))
                        with st.expander("JSON brut"):
                            st.json(result)
                    else:
                        st.error(f"Erreur {r.status_code} : {r.text}")
                except Exception as e:
                    st.error(f"Erreur : {e}")
        else:
            st.warning("Veuillez fournir un fichier audio.")

# --- TAB 5: Dialogue ---
with tabs[4]:
    st.header("Dialogue Interactif (Slot-filling)")

    d_col1, d_col2 = st.columns([1, 1])

    with d_col1:
        d_schema_input = st.text_area(
            "Schéma JSON",
            value=json.dumps(DEFAULT_SCHEMA, indent=2, ensure_ascii=False),
            height=260,
            key="d_schema",
        )
        d_schema_obj, d_schema_err = parse_schema(d_schema_input)
        if d_schema_err:
            st.error(f"JSON invalide : {d_schema_err}")

        ask_optional = st.checkbox("Demander les champs optionnels", value=False)

        if st.button("Réinitialiser le dialogue"):
            st.session_state.dialogue_state = {}
            st.rerun()

    with d_col2:
        st.markdown("**Champs collectés**")
        if st.session_state.dialogue_state:
            for k, v in st.session_state.dialogue_state.items():
                st.success(f"`{k}` → {v}")
        else:
            st.info("Aucun champ collecté pour l'instant.")

        d_audio = st.audio_input("Répondez par la voix", key="d_record")
        d_text = st.text_input("Ou par texte")

        if st.button("Envoyer", key="btn_dialogue", disabled=d_schema_obj is None):
            if not d_audio and not d_text:
                st.warning("Fournissez une réponse audio ou texte.")
            else:
                with st.spinner("Traitement..."):
                    try:
                        form_data = {
                            "collected": json.dumps(st.session_state.dialogue_state),
                            "schema": d_schema_input,
                            "ask_optional": str(ask_optional).lower(),
                        }
                        files = None
                        if d_audio:
                            files = {"audio": ("input.wav", d_audio.read(), "audio/wav")}
                        else:
                            form_data["text"] = d_text

                        r = httpx.post(f"{API_BASE_URL}/v1/dialogue-audio", files=files, data=form_data, timeout=TIMEOUT)

                        if r.status_code == 200:
                            state_json = r.headers.get("X-Dialogue-State")
                            if state_json:
                                state = json.loads(state_json)
                                st.session_state.dialogue_state = state["collected"]
                                add_to_history("Dialogue", form_data, state)
                                st.markdown(f"**Transcription :** {state.get('transcription', '—')}")
                                st.markdown(f"**Question suivante :** {state.get('next_question', '—')}")
                                if state.get("is_complete"):
                                    st.success("Dialogue terminé !")
                                st.audio(r.content, format="audio/wav")
                                st.rerun()
                            else:
                                st.error("Header X-Dialogue-State manquant")
                        else:
                            st.error(f"Erreur {r.status_code} : {r.text}")
                    except Exception as e:
                        st.error(f"Erreur : {e}")

# --- TAB 6: Historique ---
with tabs[5]:
    st.header("Historique des échanges")
    if not st.session_state.history:
        st.info("Aucun échange pour le moment.")
    else:
        if st.button("Effacer l'historique"):
            st.session_state.history = []
            st.rerun()
        for entry in reversed(st.session_state.history):
            with st.expander(f"{entry['time']} — {entry['endpoint']}"):
                col_i, col_r = st.columns(2)
                with col_i:
                    st.markdown("**Entrée**")
                    st.json(entry["input"])
                with col_r:
                    st.markdown("**Réponse**")
                    st.json(entry["response"])
