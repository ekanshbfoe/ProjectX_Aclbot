# Copyright (c) 2026 ACL community
# Licensed under the MIT License.
# This file is part of ProjectX_Aclbot

import os
import time
import logging
import urllib.request
from flask import Flask
from threading import Thread

app = Flask('')
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return "I am alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def ping_self():
    """Background task to ping itself to keep Render instance awake."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        logger.warning("RENDER_EXTERNAL_URL not set, self-pinging disabled.")
        return

    logger.info(f"Self-pinging started for: {url}")
    while True:
        try:
            # Ping every 10 minutes (600 seconds)
            time.sleep(600)
            urllib.request.urlopen(url)
            logger.debug("Self-ping successful.")
        except Exception as e:
            logger.error(f"Self-ping failed: {e}")

def keep_alive():
    """Starts the Flask server and self-pinger in background threads."""
    # Start Flask server
    t_server = Thread(target=run, daemon=True)
    t_server.start()
    
    # Start Self-pinger
    t_ping = Thread(target=ping_self, daemon=True)
    t_ping.start()

