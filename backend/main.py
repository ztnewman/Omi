import asyncio
import json
import os

import firebase_admin
from fastapi import FastAPI
from fastapi_utilities import repeat_at

from modal import Image, App, asgi_app, Secret
from routers import chat, memories, plugins, speech_profile, transcribe, screenpipe, firmware, notifications, workflow
from utils.crons.notifications import start_cron_job

if os.environ.get('SERVICE_ACCOUNT_JSON'):
    service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
    credentials = firebase_admin.credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(credentials)
else:
    firebase_admin.initialize_app()

app = FastAPI()
app.include_router(transcribe.router)
app.include_router(memories.router)
app.include_router(chat.router)
app.include_router(plugins.router)
app.include_router(speech_profile.router)
app.include_router(screenpipe.router)
app.include_router(workflow.router)
app.include_router(notifications.router)
app.include_router(workflow.router)

app.include_router(firmware.router)

modal_app = App(
    name='backend',
    secrets=[Secret.from_name("gcp-credentials"), Secret.from_name('envs')],
)
image = (
    Image.debian_slim()
    .apt_install('ffmpeg', 'git', 'unzip')
    .pip_install_from_requirements('requirements.txt')
)


@modal_app.function(
    image=image,
    keep_warm=2,
    memory=(1024, 2048),
    cpu=4,
    allow_concurrent_inputs=5,
    # timeout=24 * 60 * 60,  # avoid timeout with websocket, but then containers do not die
    # can decrease memory and cpu size?
    timeout=60 * 10,
)
@asgi_app()
def api():
    print('api')
    return app


paths = ['_temp', '_samples', '_segments', '_speech_profiles']
for path in paths:
    if not os.path.exists(path):
        os.makedirs(path)


@app.on_event('startup')
@repeat_at(cron="* * * * *")
def start_job():
    asyncio.run(start_cron_job())
