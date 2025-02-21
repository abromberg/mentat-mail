# Mentat Mail: https://mentatmail.com
# Copyright (C) 2025 Andy Bromberg andy@andybromberg.com

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>. 

import os
import json
from dotenv import load_dotenv

class EmailProcessingError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code

def load_configuration():
    load_dotenv()

    required_env_vars = ['SENDGRID_API_KEY', 'SYSTEM_PROMPT', 'DEFAULT_MODEL_SLUG', 'WHITELISTED_EMAILS', 'DEFAULT_PROVIDER']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

    api_keys = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'PERPLEXITY_API_KEY']
    found_api_keys = [key for key in api_keys if os.getenv(key)]
    if found_api_keys == []:
        raise RuntimeError(f"Missing required API keys, please add one: {', '.join(api_keys)}")

    WHITELISTED_EMAILS = [email.strip().lower() for email in os.getenv('WHITELISTED_EMAILS', '').split(',') if email.strip()]

    try:
        model_aliases = json.loads(os.getenv('MODEL_ALIASES', '{}'))
    except json.JSONDecodeError:
        model_aliases = {}

    model_mapping = {
        'gpt4omini': {'model': 'openai/gpt-4o-mini', 'name': 'Mentat [GPT-4o Mini]', 'provider': 'openai'},
        'gpt4o': {'model': 'openai/chatgpt-4o-latest', 'name': 'Mentat [GPT-4o]', 'provider': 'openai'},
        'o1': {'model': 'openai/o1', 'name': 'Mentat [o1]', 'provider': 'openai'},
        'o3mini': {'model': 'openai/o3-mini', 'name': 'Mentat [o3 Mini]', 'provider': 'openai'},
        'claude': {'model': 'anthropic/claude-3-5-sonnet-latest', 'name': 'Mentat [Claude]', 'provider': 'anthropic'},
        'geminiflash': {'model': 'gemini/gemini-2.0-flash', 'name': 'Mentat [Gemini 2.0 Flash]', 'provider': 'gemini'},
        'geminipro': {'model': 'gemini/gemini-1.5-pro', 'name': 'Mentat [Gemini Pro]', 'provider': 'gemini'},
        'sonarpro': {'model': 'perplexity/sonar-pro', 'name': 'Mentat [Sonar Pro]', 'provider': 'perplexity'}
    }

    model_mapping.update(model_aliases)

    return {
        'WHITELISTED_EMAILS': WHITELISTED_EMAILS,
        'MODEL_MAPPING': model_mapping
    } 