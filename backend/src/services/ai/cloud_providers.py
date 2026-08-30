"""Dormant codecs only. No HTTP client, credentials, or network activation.

An application-approved transport would be required for a future activation.
Current application composition always selects MockAIInsightProvider.
"""
import json
from src.schemas.ai_insight import NarrativeOutput
from src.services.ai.provider import AIInsightProvider


class OpenAICompatibleInsightProvider(AIInsightProvider):
    name = 'OPENAI_COMPATIBLE'

    def __init__(self, transport=None):
        self.transport = transport

    async def generate(self, payload, *, max_tokens=500):
        if self.transport is None:
            raise PermissionError('External AI provider activation requires approval')
        from src.services.ai.prompt_templates import build_prompt
        response = await self.transport({'messages': [{'role': 'system', 'content': build_prompt(payload)}], 'max_tokens': max_tokens, 'temperature': 0.1, 'response_format': {'type': 'json_object'}})
        return NarrativeOutput.model_validate(json.loads(response['choices'][0]['message']['content']))


class GeminiInsightProvider(OpenAICompatibleInsightProvider):
    name = 'GEMINI'

    async def generate(self, payload, *, max_tokens=500):
        if self.transport is None:
            raise PermissionError('External AI provider activation requires approval')
        from src.services.ai.prompt_templates import build_prompt
        response = await self.transport({'contents': [{'parts': [{'text': build_prompt(payload)}]}], 'generationConfig': {'maxOutputTokens': max_tokens, 'temperature': 0.1, 'responseMimeType': 'application/json'}})
        return NarrativeOutput.model_validate_json(response['candidates'][0]['content']['parts'][0]['text'])
