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
import base64
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, PlainTextContent
import litellm
from utils import debug_print, extract_email, is_email_whitelisted, format_quoted_text
from config import EmailProcessingError, load_configuration

async def process_attachments(attachments):
    message_content = []
    text_content = ""
    
    for attachment in attachments:
        try:
            debug_print(f"\nProcessing attachment: {attachment['filename']}")
            debug_print(f"Content type: {type(attachment['content'])}")
            debug_print(f"Content length: {len(attachment['content'])}")
            file_ext = os.path.splitext(attachment['filename'].lower())[1]
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}
            content_type = attachment.get('content_type')
            
            is_image = (
                file_ext in image_extensions or
                (content_type and content_type.startswith('image/'))
            )
            
            if is_image:
                image_content = base64.b64encode(attachment['content']).decode('utf-8')
                mime_type = 'png'
                if content_type and content_type.startswith('image/'):
                    mime_type = content_type.split('/')[1]
                elif file_ext in {'.jpg', '.jpeg'}:
                    mime_type = 'jpeg'
                elif file_ext in {'.gif', '.webp', '.bmp', '.tiff', '.tif', '.png'}:
                    mime_type = file_ext[1:]
                
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{mime_type};base64,{image_content}"
                    }
                })
            else:
                text_content += f"\n[Attached file: {attachment['filename']} (not an image)]"
                
        except Exception as e:
            debug_print(f"Error processing attachment {attachment['filename']}: {str(e)}")
            import traceback
            debug_print(traceback.format_exc())
            
    return message_content, text_content

async def get_ai_response(text_content, attachments, clean_to_email, subject, model_mapping):
    debug_print("\n=== Preparing AI Request ===")
    system_prompt = f"""You are an AI assistant participating in an email thread. The message you receive will contain the full email thread, with the most recent message at the top. Email threads are typically marked with ">" characters at the start of quoted lines, with more ">" characters indicating older messages.

IMPORTANT:
1. Only respond to the most recent message (the text at the top before any ">" marks)
2. Use the quoted/older messages (typically marked with ">") only for context to understand what was previously discussed and to inform your response to the most recent message. Read carefully and make sure you're paying attention to the logical sequence of the messages (most recent at the top).
3. If you're HIGHLY confident there is anything for you to respond to in the most recent message, reply with "NOREPLY" — for example: if there are multiple people on the thread and the most recent message is clearly addressed to someone else and not you, simply say "NOREPLY" - however, err on the side of responding normally; only use NOREPLY if you're confident there's nothing to reply to. Most of the time, when you're on a thread and a question is posed, it is meant for you, so do not use NOREPLY.
4. When responding in a group thread:
   - Pay attention to who the message is addressed to (look for "@name" or direct addressing)
   - Only respond if you're directly addressed or if the question/discussion is relevant to your role
   - Be mindful not to interrupt conversations between other participants

Additional context:
- The subject of the email is: {subject}
- Your email address is {clean_to_email}. As you're reviewing the thread, you may see prior messages from yourself.
- You might be addressed by the names "Mentat" or "{clean_to_email.split('@')[0]}" or something similar
- The current date is {datetime.now().strftime("%Y-%m-%d")}.

There is a possibility of a situation where you and another AI agent go back and forth endlessly in an unproductive way. If you think this might be happening, you should reply once saying that you're wondering if that's what is happening and ask a human if you should keep responding. After that, reply "NOREPLY_LOOPING" unless a human affirms you should continue. If you really think it's happening or a looping conversation is continuing, simply reply "NOREPLY_LOOPING"

Aside from those specific and IMPORTANT instructions, here are general instructions for how you should reply:

{os.getenv('SYSTEM_PROMPT')}"""

    messages = [{"role": "system", "content": system_prompt}]
    debug_print(f"System prompt prepared")

    if attachments:
        message_content = [{"type": "text", "text": text_content}]
        attachment_content, attachment_text = await process_attachments(attachments)
        message_content.extend(attachment_content)
        if attachment_text:
            message_content[0]["text"] += attachment_text
        messages.append({"role": "user", "content": message_content})
        debug_print(f"Added message with attachments")
    else:
        messages.append({"role": "user", "content": text_content})
        debug_print(f"Added text message: {text_content}")

    from_email_name = clean_to_email.split('@')[0].lower()
    debug_print(f"Looking up model for email name: {from_email_name}")
    
    model_info = model_mapping.get(from_email_name, {
        'model': f"{os.getenv('DEFAULT_PROVIDER')}/{os.getenv('DEFAULT_MODEL_SLUG')}",
        'provider': os.getenv('DEFAULT_PROVIDER')
    })
    debug_print(f"Selected model info: {model_info}")
    
    provider = model_info.get('provider')
    debug_print(f"Using provider: {provider}")
    
    api_key = os.getenv(f'{provider.upper()}_API_KEY', os.getenv('OPENAI_API_KEY'))
    if not api_key:
        debug_print(f"No API key found for provider {provider}")
        raise EmailProcessingError(f"No API key found for provider {provider}", 500)
    
    debug_print(f"Making API call to model: {model_info.get('model')}")
    try:
        response = await litellm.acompletion(
            model=model_info.get('model'),
            messages=messages,
            api_key=api_key
        )
        debug_print("API call successful")
        debug_print(f"\n=== LLM Response ===\n{response.choices[0].message.content}\n==================")
        return response.choices[0].message.content
    except Exception as e:
        debug_print(f"Error in AI API call: {str(e)}")
        raise EmailProcessingError(f"AI API error: {str(e)}", 500)

async def send_email_response(ai_response, text_content, from_email, to_email, subject, message_id, references, model_name, clean_to_email, cc_addresses=''):
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
    
    clean_subject = subject.strip() if subject else ""
    reply_subject = f"Re: {clean_subject}" if not clean_subject.startswith('Re: ') else clean_subject
    
    sending_to_email = extract_email(from_email)
    clean_response = ai_response.strip()
    quoted_text = format_quoted_text(text_content, from_email)
    full_response = clean_response + quoted_text
    
    to_emails = [extract_email(email) for email in to_email.split(',') 
                 if email.strip() and extract_email(email).lower() != clean_to_email.lower()]
    if isinstance(cc_addresses, str):
        cc_emails = [extract_email(addr.strip()) for addr in cc_addresses.split(',') 
                    if addr.strip() and extract_email(addr).lower() != clean_to_email.lower()]
    else:
        cc_emails = [extract_email(addr) for addr in cc_addresses 
                    if addr.strip() and extract_email(addr).lower() != clean_to_email.lower()]
    
    if extract_email(from_email).lower() != clean_to_email.lower() and extract_email(from_email) not in to_emails:
        to_emails = [extract_email(from_email)] + to_emails
    
    if not to_emails:
        raise EmailProcessingError("No valid recipient email addresses", 400)
    
    email_data = {
        "personalizations": [{
            "to": [{"email": email} for email in to_emails],
            "cc": [{"email": email} for email in cc_emails] if cc_emails else None
        }],
        "from": {
            "email": clean_to_email,
            "name": model_name
        },
        "subject": reply_subject,
        "content": [{
            "type": "text/plain",
            "value": full_response
        }],
        "reply_to": {
            "email": clean_to_email,
            "name": model_name
        },
        "headers": {
            "X-Priority": "3"
        }
    }
    
    if message_id:
        email_data["headers"]["In-Reply-To"] = message_id
    if references:
        email_data["headers"]["References"] = references
    
    if not email_data["personalizations"][0].get("cc"):
        del email_data["personalizations"][0]["cc"]
    
    try:
        response = sg.client.mail.send.post(request_body=email_data)
        debug_print(f"Email response sent successfully with status code: {response.status_code}")
        return True, "Email processed and response sent successfully", 200
    except Exception as e:
        debug_print(f"\n=== SendGrid Error ===")
        if hasattr(e, 'body'):
            debug_print(f"Error Response: {e.body}")
        raise EmailProcessingError(f"Failed to send email: {str(e)}", 500)

async def process_and_reply_to_email(from_email, to_email, subject, text_content, message_id=None, references=None, attachments=None, cc_addresses=''):
    try:
        sender_email = extract_email(from_email).lower()
        config = load_configuration()
        
        if not is_email_whitelisted(sender_email, config['WHITELISTED_EMAILS']):
            debug_print(f"Rejected email from non-whitelisted sender: {sender_email}")
            raise EmailProcessingError("Sender email not whitelisted", 403)
        
        to_addresses = [extract_email(addr.strip()) for addr in to_email.split(',') if addr.strip()]
        if isinstance(cc_addresses, str):
            cc_list = [extract_email(addr.strip()) for addr in cc_addresses.split(',') if addr.strip()]
        else:
            cc_list = [extract_email(addr) for addr in cc_addresses if addr.strip()]
        
        all_addresses = to_addresses + cc_list
        agent_addresses = [addr for addr in all_addresses if addr.split('@')[0].lower() in config['MODEL_MAPPING']]
        
        if not agent_addresses:
            clean_to_email = all_addresses[0]
            from_email_name = clean_to_email.split('@')[0]
        else:
            clean_to_email = agent_addresses[0]
            from_email_name = clean_to_email.split('@')[0]
        
        model_data = config['MODEL_MAPPING'].get(from_email_name.lower(), {
            'model': os.getenv('DEFAULT_MODEL_SLUG'),
            'name': f"Mentat [{os.getenv('DEFAULT_MODEL_SLUG')}]"
        })
        
        debug_print(f"\n=== Processing Email ===")
        debug_print(f"From: {from_email}")
        debug_print(f"To: {', '.join(to_addresses)}")
        debug_print(f"CC: {', '.join(cc_list)}")
        debug_print(f"Selected agent address: {clean_to_email}")
        debug_print(f"Subject: {subject}")
        debug_print(f"Has attachments: {bool(attachments)}")
        
        ai_response = await get_ai_response(text_content, attachments, clean_to_email, subject, config['MODEL_MAPPING'])
        
        if any(indicator.lower() in ai_response.lower() for indicator in ["NOREPLY"]):
            debug_print("AI indicated no reply needed - stopping processing")
            return True, "AI determined no reply was needed", 200
        if any(indicator.lower() in ai_response.lower() for indicator in ["NOREPLY_LOOPING"]):
            debug_print("AI indicated looping conversation - stopping processing")
            return True, "AI indicated looping conversation - stopping processing", 200
        
        return await send_email_response(
            ai_response=ai_response,
            text_content=text_content,
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            message_id=message_id,
            references=references,
            model_name=model_data['name'],
            clean_to_email=clean_to_email,
            cc_addresses=cc_addresses
        )
        
    except EmailProcessingError as e:
        debug_print(f"Email processing error: {str(e)}")
        return False, str(e), e.status_code
    except Exception as e:
        error_msg = f"Error processing email: {str(e)}"
        debug_print(error_msg)
        import traceback
        debug_print(traceback.format_exc())
        return False, error_msg, 500