import asyncio
import json
import os
import re
from typing import Any, Dict

import boto3


class NovaService:
	"""Minimal Bedrock Nova client focused on JSON responses."""

	def __init__(self) -> None:
		self.model_id = os.getenv("NOVA_MODEL_ID", "amazon.nova-lite-v1:0")
		self.region = os.getenv("AWS_REGION", "eu-west-1")
		self._client = None

	def _client_runtime(self):
		if self._client is None:
			self._client = boto3.client("bedrock-runtime", region_name=self.region)
		return self._client

	async def generate_json(
		self,
		*,
		system_prompt: str,
		user_prompt: str,
		max_tokens: int = 1200,
		temperature: float = 0.2,
	) -> Dict[str, Any]:
		text = await asyncio.to_thread(
			self._converse_text,
			system_prompt,
			user_prompt,
			max_tokens,
			temperature,
		)
		parsed = self._extract_json(text)
		if not isinstance(parsed, dict):
			raise ValueError("Nova response did not contain a valid JSON object")
		return parsed

	def _converse_text(
		self,
		system_prompt: str,
		user_prompt: str,
		max_tokens: int,
		temperature: float,
	) -> str:
		resp = self._client_runtime().converse(
			modelId=self.model_id,
			system=[{"text": system_prompt}],
			messages=[
				{
					"role": "user",
					"content": [{"text": user_prompt}],
				}
			],
			inferenceConfig={
				"maxTokens": max_tokens,
				"temperature": temperature,
				"topP": 0.9,
			},
		)

		content = (
			resp.get("output", {})
			.get("message", {})
			.get("content", [])
		)
		parts = [part.get("text", "") for part in content if isinstance(part, dict)]
		text = "\n".join([p for p in parts if p]).strip()
		if not text:
			raise ValueError("Empty response from Nova model")
		return text

	def _extract_json(self, text: str) -> Any:
		cleaned = text.strip()
		cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
		cleaned = re.sub(r"^```", "", cleaned)
		cleaned = re.sub(r"```$", "", cleaned).strip()

		try:
			return json.loads(cleaned)
		except Exception:
			pass

		start = cleaned.find("{")
		if start == -1:
			return None

		depth = 0
		for i in range(start, len(cleaned)):
			ch = cleaned[i]
			if ch == "{":
				depth += 1
			elif ch == "}":
				depth -= 1
				if depth == 0:
					candidate = cleaned[start : i + 1]
					try:
						return json.loads(candidate)
					except Exception:
						return None
		return None


nova_service = NovaService()
