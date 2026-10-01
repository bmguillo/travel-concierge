# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types


async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


from app.tools import (
    add_destination,
    convert_currency,
    find_nearby_places,
    generate_destination_image,
    generate_destination_video,
    geocode_address,
    get_destination_details,
    get_live_destination_weather,
    save_travel_itinerary,
    search_destinations,
)


import json
import os

from google.adk.code_executors import AgentEngineSandboxCodeExecutor


def _get_code_executor() -> AgentEngineSandboxCodeExecutor:
    metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
    agent_engine_name = None
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                agent_engine_name = data.get("remote_agent_runtime_id")
        except Exception:
            pass

    if agent_engine_name:
        return AgentEngineSandboxCodeExecutor(agent_engine_resource_name=agent_engine_name)
    return AgentEngineSandboxCodeExecutor()


from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from app.a2ui_utils import a2ui_callback

_a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = _a2ui_schema_manager.generate_system_prompt(
    role_description=(
        "You are an expert, friendly Travel Concierge AI assistant. "
        "Use your tools to search destination catalog records in Firestore, retrieve destination details, "
        "add new destinations, convert currencies with live exchange rates, check real-time destination weather, "
        "geocode landmark addresses to coordinates, search nearby places, generate travel image postcards, and generate short video previews for destinations using Google Omni. "
        "You can also safely execute Python code in a sandbox to run computations, budget calculations, or data analysis. "
        "IMPORTANT: You MUST remember all user allergies (e.g. food, medical, environmental allergies), dietary restrictions, and personal preferences across all conversations using your memory bank tool. "
        "Always check preloaded memories for user allergies before suggesting restaurants, food items, or travel activities, and never recommend anything containing user allergens."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=_get_code_executor(),
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        add_destination,
        save_travel_itinerary,
        convert_currency,
        get_live_destination_weather,
        geocode_address,
        find_nearby_places,
        generate_destination_image,
        generate_destination_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)

