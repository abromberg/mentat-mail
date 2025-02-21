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
import re
from datetime import datetime

def debug_print(*args, **kwargs):
    if os.getenv('FLASK_DEBUG') == '1':
        print(*args, **kwargs)

def extract_email(email_string):
    bracket_match = re.findall(r'<([^<>]+@[^<>]+)>', email_string)
    if bracket_match:
        return bracket_match[-1].strip()
    
    email_match = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', email_string)
    if email_match:
        return email_match[-1].strip()
    
    return email_string.strip()

def is_email_whitelisted(email, whitelisted_emails):
    email = email.lower()
    email_domain = email.split('@')[1] if '@' in email else ''

    for whitelisted_email in whitelisted_emails:
        if whitelisted_email == '*' or whitelisted_email == '*@*' or whitelisted_email == '*@*.*':
            return True
        whitelisted_email = whitelisted_email.lower()

        if whitelisted_email.startswith('*@'):
            whitelisted_domain = whitelisted_email[2:]
            if email_domain == whitelisted_domain:
                return True
            
        elif email == whitelisted_email:
            return True
    
    return False

def format_quoted_text(text_content, from_email):
    original_text = text_content.strip()
    formatted_date = datetime.now().strftime("%a, %d %b %Y %I:%M %p")
    quoted_text = f"\n\nOn {formatted_date} {from_email} wrote:\n"
    
    lines = original_text.split('\n')
    quoted_lines = []
    for line in lines:
        quote_level = 0
        while line.startswith('>'):
            quote_level += 1
            line = line[1:].lstrip()
        
        if line.strip():
            quoted_lines.append('>' * (quote_level + 1) + ' ' + line)
        else:
            quoted_lines.append('>' * (quote_level + 1))
    
    return quoted_text + '\n'.join(quoted_lines) 