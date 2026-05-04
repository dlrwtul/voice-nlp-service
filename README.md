# Voice NLP Service

Un microservice générique qui transforme de l'audio brut en données JSON structurées.  
Il combine deux technologies d'IA : la **reconnaissance vocale** (ASR) et l'**extraction d'informations** (NLP).

> **Contexte d'origine** : développé pour [Faypass](https://github.com/faypass), une plateforme de transport au Sénégal, pour permettre aux passagers de rechercher un trajet à la voix — en français ou en wolof. Mais le service est **complètement générique** : il accepte n'importe quel schéma de données.

---

## Table des matières

1. [Ce que fait ce service](#1-ce-que-fait-ce-service)
2. [Cours : comprendre l'ASR](#2-cours--comprendre-lasr)
3. [Cours : comprendre le NLP](#3-cours--comprendre-le-nlp)
4. [Cours : comment l'IA extrait des données structurées](#4-cours--comment-lia-extrait-des-données-structurées)
5. [Architecture du service](#5-architecture-du-service)
6. [Les trois endpoints](#6-les-trois-endpoints)
7. [Démarrage rapide](#7-démarrage-rapide)
8. [Configuration](#8-configuration)
9. [Exemples d'utilisation](#9-exemples-dutilisation)
10. [Personnaliser l'extraction : le système de schéma](#10-personnaliser-lextraction--le-système-de-schéma)
11. [Déploiement en production](#11-déploiement-en-production)

---

## 1. Ce que fait ce service

En une phrase : **vous envoyez un fichier audio + une description de ce que vous voulez extraire, le service vous retourne un JSON propre.**

Exemple concret avec Faypass :

```
Audio : "Je veux aller à Ziguinchor depuis Dakar demain pour deux personnes"

               ┌─────────────────────────────┐
               │      Voice NLP Service      │
               │                             │
  audio  ───►  │  1. Whisper (ASR)           │
               │     → transcrit l'audio     │
               │                             │
               │  2. LLM via Ollama (NLP)    │  ───►  JSON
               │     → extrait les champs    │
               └─────────────────────────────┘

JSON produit :
{
  "origin_city": "Dakar",
  "destination_city": "Ziguinchor",
  "date": "2026-05-05",
  "passenger_count": 2,
  "service_type": null
}
```

Le service peut s'adapter à n'importe quel domaine : réservation de billet, commande e-commerce, prise de rendez-vous médical, etc. Vous changez le schéma, le service s'adapte.

---

## 2. Cours : comprendre l'ASR

### Qu'est-ce que l'ASR ?

**ASR** signifie *Automatic Speech Recognition* — en français : **reconnaissance automatique de la parole**. C'est la technologie qui transforme un enregistrement audio en texte écrit.

Quand vous utilisez Siri, Google Assistant, ou les sous-titres automatiques de YouTube, c'est de l'ASR.

### Comment ça fonctionne (simplifié)

Un fichier audio n'est qu'une suite de nombres représentant des vibrations sonores dans le temps (une onde). Le modèle ASR analyse ces vibrations et les associe à des mots.

```
Onde sonore (fichier .wav) :
  ▁▂▄▇█▇▄▂▁▂▄▆█▆▄▂▁ ...

   ↓ Le modèle analyse les fréquences

Séquence de phonèmes :
  /ʒ/ /ə/ /v/ /ø/ /a/ /l/ /e/ ...

   ↓ Les phonèmes s'assemblent en mots

Texte :
  "Je veux aller à Dakar"
```

Les modèles modernes (comme Whisper) ne passent plus vraiment par les phonèmes explicitement — ils apprennent directement de gigantesques corpus audio/texte grâce aux **réseaux de neurones transformeurs**.

### Whisper : le modèle utilisé ici

Ce service utilise **[Whisper](https://github.com/openai/whisper)**, développé par OpenAI et rendu public en 2022. C'est l'un des modèles ASR les plus précis disponibles en open-source.

On utilise plus précisément **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)**, une réimplémentation optimisée qui est 2 à 4× plus rapide avec la même précision.

**Les tailles de modèles disponibles :**

| Modèle | RAM ~requise | Langues | Vitesse | Usage recommandé |
|--------|-------------|---------|---------|-----------------|
| `tiny` | 1 GB | 99 | ⚡⚡⚡⚡ | Tests, prototypes |
| `base` | 1 GB | 99 | ⚡⚡⚡ | Développement |
| `small` | 2 GB | 99 | ⚡⚡ | **Défaut ici** — bon compromis |
| `medium` | 5 GB | 99 | ⚡ | Production précision |
| `large-v3` | 10 GB | 99 | 🐢 | Précision maximale |

Whisper est **multilingue** : il détecte automatiquement la langue parlée. Il supporte le français, l'anglais, l'arabe, et même partiellement le wolof et d'autres langues d'Afrique de l'Ouest.

**Ce que Whisper retourne :**

```json
{
  "text": "Je veux aller à Ziguinchor depuis Dakar demain",
  "language": "fr",
  "confidence": 0.998,
  "duration_seconds": 4.32
}
```

- `text` : la transcription complète
- `language` : la langue détectée (code ISO 639-1)
- `confidence` : niveau de certitude sur la langue détectée (0 à 1)
- `duration_seconds` : durée de l'audio

### Formats audio acceptés

Grâce à **ffmpeg** (installé dans le Docker), le service accepte : `.wav`, `.mp3`, `.ogg`, `.m4a`, `.flac`, `.webm`, et tout format que ffmpeg sait décoder.

---

## 3. Cours : comprendre le NLP

### Qu'est-ce que le NLP ?

**NLP** signifie *Natural Language Processing* — en français : **traitement automatique du langage naturel**. C'est la branche de l'IA qui donne aux ordinateurs la capacité de comprendre, d'analyser et de générer du texte humain.

Le NLP englobe de nombreuses tâches :
- **Extraction d'entités** (*NER* — Named Entity Recognition) : identifier les noms de lieux, personnes, dates...
- **Classification de l'intention** (*Intent detection*) : comprendre ce que l'utilisateur veut faire
- **Analyse de sentiment** : détecter si un texte est positif, négatif, neutre
- **Question-réponse** : répondre à des questions à partir d'un texte
- **Génération de texte** : produire du texte cohérent

Ce service utilise principalement **l'extraction d'entités** et **la classification**.

### Les LLM : la révolution du NLP

Avant 2020, chaque tâche NLP nécessitait un modèle spécialisé entraîné exprès. Extraire des dates ? Un modèle. Détecter des villes ? Un autre modèle.

Les **LLM** (*Large Language Models* — Grands Modèles de Langage) ont tout changé. Ces modèles, entraînés sur des milliards de textes, sont capables de faire toutes ces tâches à la fois, juste en leur donnant des instructions en langage naturel (un *prompt*).

**GPT-4, Claude, Llama, Gemini** : tous sont des LLM.

### Ollama : faire tourner un LLM localement

Ce service utilise **[Ollama](https://ollama.com/)**, un outil qui permet de faire tourner des LLM **sur votre propre machine ou serveur**, sans envoyer vos données vers un cloud externe.

C'est crucial pour la confidentialité : les conversations des utilisateurs de Faypass ne quittent jamais l'infrastructure.

Le modèle utilisé par défaut est **`llama3.2:3b`** — un LLM de Meta, avec 3 milliards de paramètres. Il est compact (2 GB), rapide sur CPU, et suffisamment capable pour l'extraction structurée.

```
Llama 3.2 3B :
  - Développé par : Meta
  - Paramètres : 3 milliards
  - RAM nécessaire : ~3 GB
  - Langues : multilingue (fr, en, es, de...)
  - Licence : open-source (Meta Llama License)
```

---

## 4. Cours : comment l'IA extrait des données structurées

### Le problème : du texte libre vers du JSON

L'utilisateur parle librement. Son message peut être :
- `"Je veux aller à Ziguinchor depuis Dakar demain pour deux personnes"`
- `"Dakar Thiès yoon bi tey"` (en wolof : "route Dakar-Thiès aujourd'hui")
- `"Un sept-place pour Thiès s'il vous plaît, on est trois"`

Toutes ces phrases veulent dire la même chose mais sont formulées différemment. Il faut en extraire :

```json
{ "origin_city": "Dakar", "destination_city": "Thiès", "date": "2026-05-04", "passenger_count": 3, "service_type": "sept-place" }
```

### La technique : le *prompt engineering*

On ne réentraîne pas le LLM. On lui donne des **instructions précises** (un *system prompt*) qui lui expliquent exactement quoi faire et dans quel format répondre.

Voici un exemple simplifié du prompt système généré par ce service :

```
You are a structured data extraction assistant.
Context: Application de transport en commun au Sénégal

Extract the following fields from the user's text:
  - "origin_city" (string, REQUIRED): Ville de départ
  - "destination_city" (string, REQUIRED): Ville d'arrivée
  - "date" (string "YYYY-MM-DD", optional): Date du voyage (today is 2026-05-04)
  - "passenger_count" (integer, optional): Nombre de passagers
  - "service_type" (one of: ["bus", "minibus", "sept-place"], optional): Type de véhicule

Hints:
- Villes: Dakar, Thiès, Ziguinchor, Saint-Louis, Kaolack, Touba, Mbour, Tambacounda

Rules:
- Return ONLY valid JSON, no markdown, no explanation.
- Use null for fields that are absent or unclear.
- For relative dates ("tomorrow", "demain"), resolve to YYYY-MM-DD using today = 2026-05-04.
- "missing_fields" must list required fields that are null.
- "confidence" is a float between 0 and 1.
```

Le LLM reçoit ce prompt + le texte de l'utilisateur, et répond avec du JSON pur.

### Pourquoi `temperature: 0` ?

La *température* contrôle le niveau d'aléatoire dans les réponses du LLM :
- **température haute (0.8–1.0)** → réponses variées, créatives (utile pour de la rédaction)
- **température basse (0.0)** → réponses déterministes, répétables (idéal pour l'extraction de données)

Ici on veut que `"demain"` donne toujours `"2026-05-05"`, pas une interprétation différente à chaque appel. On force donc `temperature: 0`.

### Résolution des dates relatives

C'est un exemple de raisonnement que le LLM effectue grâce au prompt :

```
Texte : "demain matin"
Today injected dans le prompt : "2026-05-04"

LLM résout : demain = 2026-05-05
Retourne : "date": "2026-05-05"
```

Sans injecter la date du jour dans le prompt, le LLM ne saurait pas quelle date correspond à "demain" (il n'a pas accès à l'heure courante).

---

## 5. Architecture du service

```
┌──────────────────────────────────────────────────────┐
│                    Voice NLP Service                  │
│                    (FastAPI / Python)                  │
│                                                       │
│  ┌─────────────┐   ┌─────────────┐   ┌────────────┐ │
│  │ /transcribe │   │  /extract   │   │/voice-to-  │ │
│  │  (ASR only) │   │ (NLP only)  │   │   json     │ │
│  └──────┬──────┘   └──────┬──────┘   └─────┬──────┘ │
│         │                 │                 │        │
│  ┌──────▼──────┐          │          ┌──────▼──────┐ │
│  │   Whisper   │          │          │   Whisper   │ │
│  │   Service   │          │          │   Service   │ │
│  └─────────────┘          │          └──────┬──────┘ │
│                    ┌──────▼──────┐          │        │
│                    │   Ollama    │   ┌──────▼──────┐ │
│                    │   Service   │◄──│   Ollama    │ │
│                    └─────────────┘   │   Service   │ │
│                                      └─────────────┘ │
└──────────────────────────────────────────────────────┘
         │                       │
         ▼                       ▼
  ┌─────────────┐       ┌─────────────────┐
  │ faster-     │       │ Ollama server   │
  │ whisper     │       │ (conteneur      │
  │ (in-process)│       │  séparé)        │
  └─────────────┘       └─────────────────┘
```

**Deux conteneurs Docker :**

| Conteneur | Rôle | Port |
|-----------|------|------|
| `voice-nlp` | API FastAPI + Whisper en mémoire | `8100` |
| `ollama` | Serveur LLM (Llama 3.2) | `11434` |

**Deux services Python :**

| Service | Fichier | Responsabilité |
|---------|---------|---------------|
| `whisper_service.py` | `app/services/asr/` | Charge le modèle Whisper, transcrit l'audio |
| `ollama_service.py` | `app/services/nlp/` | Construit le prompt, appelle Ollama, parse le JSON |

---

## 6. Les trois endpoints

### `POST /v1/transcribe` — ASR pur

Envoie un fichier audio, reçoit sa transcription texte.

```
Entrée  : multipart/form-data  →  audio (fichier)
Sortie  : JSON
```

```json
{
  "text": "Je veux aller à Ziguinchor depuis Dakar demain",
  "language": "fr",
  "confidence": 0.998,
  "duration_seconds": 4.32
}
```

---

### `POST /v1/extract` — NLP pur

Envoie du texte + un schéma, reçoit les données extraites.

```
Entrée  : application/json  →  { text, schema, today? }
Sortie  : JSON
```

```json
{
  "extracted": {
    "origin_city": "Dakar",
    "destination_city": "Ziguinchor",
    "date": "2026-05-05",
    "passenger_count": 2,
    "service_type": null
  },
  "missing_fields": [],
  "confidence": 0.95,
  "raw_text": "Je veux aller à Ziguinchor depuis Dakar demain pour deux personnes"
}
```

---

### `POST /v1/voice-to-json` — Pipeline complet 🔥

Envoie un fichier audio + un schéma, reçoit directement le JSON structuré.  
C'est la combinaison des deux endpoints précédents en un seul appel.

```
Entrée  : multipart/form-data  →  audio (fichier) + schema (JSON encodé) + today? (optionnel)
Sortie  : JSON
```

```json
{
  "transcription": {
    "text": "Je veux aller à Ziguinchor depuis Dakar demain pour deux personnes",
    "language": "fr",
    "confidence": 0.998,
    "duration_seconds": 4.32
  },
  "extraction": {
    "extracted": {
      "origin_city": "Dakar",
      "destination_city": "Ziguinchor",
      "date": "2026-05-05",
      "passenger_count": 2,
      "service_type": null
    },
    "missing_fields": [],
    "confidence": 0.95,
    "raw_text": "Je veux aller à Ziguinchor depuis Dakar demain pour deux personnes"
  }
}
```

---

## 7. Démarrage rapide

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) et [Docker Compose](https://docs.docker.com/compose/install/)
- ~5 GB d'espace disque (modèles Whisper + Llama)
- Pas de GPU requis (CPU suffit pour les petits modèles)

### Lancer le service

```bash
# 1. Cloner le repo
git clone https://github.com/<votre-org>/voice-nlp-service.git
cd voice-nlp-service

# 2. Copier la configuration
cp .env.example .env

# 3. Démarrer les deux conteneurs
docker compose up -d

# 4. Télécharger le modèle LLM dans Ollama (à faire une seule fois)
docker compose exec ollama ollama pull llama3.2:3b

# 5. Vérifier que tout fonctionne
curl http://localhost:8100/health
```

Réponse attendue :
```json
{"status": "ok", "whisper_model": "small", "ollama_model": "llama3.2:3b"}
```

La documentation interactive Swagger est disponible sur : http://localhost:8100/docs  
Le guide HTML intégré est sur : http://localhost:8100/guide

### Tester avec les exemples inclus

```bash
# Installer httpx (client HTTP Python)
pip install httpx

# Lancer les tests smoke
python test_extract.py
```

Ce script teste trois cas :
1. Recherche de trajet en **français** : `"Je veux aller à Ziguinchor depuis Dakar demain matin pour deux personnes"`
2. Recherche de trajet en **wolof** : `"Dakar Thiès yoon bi tey"` (route Dakar-Thiès aujourd'hui)
3. Commande e-commerce en **anglais** : `"I'd like to order two blue t-shirts in size large"`

---

## 8. Configuration

Toutes les variables sont dans `.env` (copié depuis `.env.example`) :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `WHISPER_MODEL` | `small` | Taille du modèle Whisper : `tiny`, `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` ou `cuda` (GPU Nvidia) |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL du serveur Ollama |
| `OLLAMA_MODEL` | `llama3.2:3b` | Modèle LLM à utiliser |
| `OLLAMA_TIMEOUT` | `30` | Timeout en secondes pour les appels LLM |
| `API_KEYS` | *(vide)* | Clés API séparées par des virgules. Vide = pas d'authentification |
| `MAX_AUDIO_DURATION_SECONDS` | `120` | Durée maximale de l'audio accepté |
| `LOG_LEVEL` | `INFO` | Niveau de log : `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Activer l'authentification par clé API

```bash
# Dans .env
API_KEYS=ma-cle-secrete-1,ma-cle-secrete-2
```

Puis dans vos requêtes :
```bash
curl -H "X-API-Key: ma-cle-secrete-1" http://localhost:8100/v1/transcribe ...
```

### Changer de modèle LLM

```bash
# Télécharger un modèle plus puissant
docker compose exec ollama ollama pull llama3.1:8b

# Mettre à jour .env
OLLAMA_MODEL=llama3.1:8b

# Redémarrer le service
docker compose restart voice-nlp
```

---

## 9. Exemples d'utilisation

### Exemple 1 : Transcription d'un audio

```bash
curl -X POST http://localhost:8100/v1/transcribe \
  -F "audio=@mon_audio.wav"
```

### Exemple 2 : Extraction à partir de texte (NLP seul)

```bash
curl -X POST http://localhost:8100/v1/extract \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Je voudrais un billet pour Thiès ce vendredi, deux adultes",
    "today": "2026-05-04",
    "schema": {
      "context": "Plateforme de transport Faypass, Sénégal",
      "fields": [
        {"name": "destination_city", "type": "string",  "description": "Ville de destination", "required": true},
        {"name": "date",             "type": "date",    "description": "Date du voyage",        "required": false},
        {"name": "passenger_count",  "type": "integer", "description": "Nombre de passagers",   "required": false}
      ],
      "hints": ["Villes principales: Dakar, Thiès, Ziguinchor, Saint-Louis, Kaolack"]
    }
  }'
```

### Exemple 3 : Pipeline vocal complet (Python)

```python
import httpx
import json

schema = {
    "context": "Plateforme de transport Faypass, Sénégal",
    "fields": [
        {"name": "origin_city",      "type": "string",  "description": "Ville de départ",  "required": True},
        {"name": "destination_city", "type": "string",  "description": "Ville d'arrivée",  "required": True},
        {"name": "date",             "type": "date",    "description": "Date du voyage",   "required": False},
        {"name": "passenger_count",  "type": "integer", "description": "Nb de passagers",  "required": False},
    ],
    "hints": ["Villes: Dakar, Thiès, Ziguinchor, Saint-Louis, Kaolack, Touba"],
}

with open("audio.wav", "rb") as f:
    response = httpx.post(
        "http://localhost:8100/v1/voice-to-json",
        files={"audio": ("audio.wav", f, "audio/wav")},
        data={
            "schema": json.dumps(schema),
            "today": "2026-05-04",
        },
        timeout=60,
    )

result = response.json()
print("Transcription :", result["transcription"]["text"])
print("Données extraites :", result["extraction"]["extracted"])
```

---

## 10. Personnaliser l'extraction : le système de schéma

Le schéma est le cœur de la flexibilité de ce service. Vous définissez exactement ce que vous voulez extraire.

### Structure d'un schéma

```json
{
  "context": "Description de votre application pour guider le LLM",
  "fields": [ ... ],
  "hints": [ ... ]
}
```

### Les types de champs disponibles

| Type | Description | Exemple de sortie |
|------|-------------|-------------------|
| `string` | Texte libre | `"Dakar"` |
| `integer` | Nombre entier | `2` |
| `float` | Nombre décimal | `3.5` |
| `boolean` | Vrai ou faux | `true` |
| `date` | Date au format `YYYY-MM-DD` | `"2026-05-05"` |
| `datetime` | Date+heure ISO 8601 | `"2026-05-05T14:30:00"` |
| `enum` | Valeur parmi une liste fixe | `"bus"` |

### Exemple : prise de rendez-vous médical

```json
{
  "context": "Application de prise de rendez-vous pour une clinique",
  "fields": [
    {"name": "patient_name",   "type": "string",   "description": "Nom complet du patient",           "required": true},
    {"name": "appointment_dt", "type": "datetime", "description": "Date et heure du rendez-vous",     "required": true},
    {"name": "specialty",      "type": "enum",     "description": "Spécialité médicale",              "required": true,
     "enum_values": ["généraliste", "cardiologue", "pédiatre", "dermatologue"]},
    {"name": "is_urgent",      "type": "boolean",  "description": "Si le patient signale une urgence", "required": false}
  ],
  "hints": [
    "Le cabinet est ouvert du lundi au samedi de 8h à 18h",
    "Les urgences sont dirigées vers le Dr. Diallo"
  ]
}
```

Texte : `"Bonjour, Aminata Diop voudrait voir un cardiologue mardi prochain à 10h, c'est urgent"`

Résultat :
```json
{
  "patient_name": "Aminata Diop",
  "appointment_dt": "2026-05-12T10:00:00",
  "specialty": "cardiologue",
  "is_urgent": true
}
```

### Le champ `hints`

Les `hints` sont des informations contextuelles données au LLM pour améliorer la précision. Par exemple :
- **Listes de valeurs connues** : noms de villes, produits, catégories
- **Règles métier** : `"Si l'utilisateur dit 'demain matin', supposer 8h00"`
- **Corrections phonétiques** : `"'Ziguinchor' peut être prononcé 'Ziginchor'"`

---

## 11. Déploiement en production

### Checklist avant de déployer

- [ ] Définir des clés API dans `API_KEYS` (ne pas laisser l'accès ouvert)
- [ ] Choisir le modèle Whisper adapté à vos contraintes (RAM vs précision)
- [ ] S'assurer qu'Ollama a téléchargé le modèle LLM avant le premier démarrage
- [ ] Configurer `MAX_AUDIO_DURATION_SECONDS` selon votre cas d'usage
- [ ] Mettre les volumes Docker sur un disque persistant (modèles = plusieurs GB)

### Sur un serveur avec GPU

```bash
# .env
WHISPER_DEVICE=cuda
WHISPER_MODEL=large-v3
```

```yaml
# docker-compose.yml — ajouter à whisper-nlp service
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### Choisir un modèle LLM plus puissant

Pour de meilleures extractions sur des textes complexes ou ambigus :

```bash
# Modèle 8B — meilleure compréhension, plus lent
docker compose exec ollama ollama pull llama3.1:8b

# Modèle multilingue spécialisé
docker compose exec ollama ollama pull mistral:7b
```

---

## Stack technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| API Framework | [FastAPI](https://fastapi.tiangolo.com/) | 0.115 |
| ASR | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 1.1.1 |
| LLM Runtime | [Ollama](https://ollama.com/) | latest |
| LLM Modèle | [Llama 3.2](https://llama.meta.com/) | 3B paramètres |
| Validation | [Pydantic](https://docs.pydantic.dev/) | 2.9 |
| HTTP Client | [httpx](https://www.python-httpx.org/) | 0.27 |
| Serveur ASGI | [Uvicorn](https://www.uvicorn.org/) | 0.30 |
| Conteneurisation | Docker + Docker Compose | — |

---

## Licence

Ce service est développé dans le cadre du projet Faypass.
