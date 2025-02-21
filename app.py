# Mentat Mail: https://andybromberg.com/mentat-mail
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

from flask import Flask, request
import os
import re
from email_processor import process_and_reply_to_email
from utils import debug_print
from config import load_configuration, EmailProcessingError

app = Flask(__name__)
config = load_configuration()

@app.route('/inbound', methods=['POST'])
async def inbound_parse():
    try:
        sender = request.form.get('from', '')
        subject = request.form.get('subject', '')
        original_message_id = request.form.get('Message-ID') or request.form.get('message-id')
        references = request.form.get('References', '')
        
        if original_message_id:
            thread_references = f"{references} {original_message_id}" if references else original_message_id
        else:
            thread_references = None

        debug_print("\n=== Incoming Request ===")
        debug_print("Headers:", dict(request.headers))
        debug_print("Form data:", dict(request.form))
        debug_print("Files:", len(request.files))

        text = request.form.get('text', '')
        html = request.form.get('html', '')
        to = request.form.get('to', '')
        
        debug_print("\n=== Email Content Debug ===")
        debug_print("Text content:")
        debug_print(text)
        debug_print("\nHTML content:")
        debug_print(html)
        debug_print("=========================\n")
        
        if text:
            try:
                if isinstance(text, bytes):
                    text.decode('utf-8')
                else:
                    text.encode('utf-8').decode('utf-8')
                content = text.strip()
            except UnicodeError:
                content = "No text content provided"
        elif html:
            content = re.sub('<[^<]+?>', '', html).strip()
        else:
            content = "No text content provided"
        
        attachments = []
        for filename, file in request.files.items():
            try:
                content_bytes = file.read()
                content_type = file.content_type if hasattr(file, 'content_type') else None
                attachments.append({
                    'filename': filename,
                    'content': content_bytes,
                    'content_type': content_type
                })
                debug_print(f"Processed attachment: {filename} (size: {len(content_bytes)} bytes)")
            except Exception as e:
                debug_print(f"Error processing attachment {filename}: {str(e)}")
        
        success, message, status_code = await process_and_reply_to_email(
            from_email=sender,
            to_email=to,
            subject=subject,
            text_content=content,
            message_id=original_message_id,
            references=thread_references,
            attachments=attachments if attachments else None,
            cc_addresses=request.form.get('cc', '')
        )
        
        if success:
            return "OK", 200
        else:
            return message, status_code
            
    except Exception as e:
        error_msg = f"Error processing inbound email: {str(e)}"
        debug_print(error_msg)
        import traceback
        debug_print(traceback.format_exc())
        return error_msg, 400

@app.route('/ping', methods=['GET'])
def ping():
    return "OK", 200

if __name__ == '__main__':
    debug = os.getenv("FLASK_DEBUG") == "1"
    if os.getenv('FLASK_ENV') == 'development':
        app.run(debug=debug, port=5001, host='0.0.0.0') 
    else:
        app.run(debug=debug) 
