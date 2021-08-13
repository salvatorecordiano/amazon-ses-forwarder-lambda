import os
import boto3
import email
import re
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase

region = os.environ['REGION']
bucket_name = os.environ['BUCKET_NAME']

def get_message_from_s3(message_id):

    # Create a new S3 client.
    client_s3 = boto3.client('s3', region_name=region)
    # Get the email object from the S3 bucket.
    object_s3 = client_s3.get_object(Bucket=bucket_name, Key=message_id)
    # Read the content of the message.
    return object_s3['Body'].read()

def create_message(message_id, file):

    sender = os.environ['MAIL_SENDER']
    recipient = os.environ['MAIL_RECIPIENT']

    separator = ";"

    # Parse the email body.
    mail_object = email.message_from_string(file.decode('utf-8'))

    # The subject of the email.
    subject = mail_object['Subject']
    
    email_to = mail_object.get_all('To')
    email_from = mail_object.get_all('From')
    email_cc = mail_object.get_all('Cc')

    # The body text of the email.
    body_text = ('This is a forwarded message'
        + "\nFrom: " + (separator.join(email_from) if hasattr(email_from, '__iter__') else 'empty')
        + "\nTo: " + (separator.join(email_to) if hasattr(email_to, '__iter__') else 'empty')
        + "\nCc: " + (separator.join(email_cc) if hasattr(email_cc, '__iter__') else 'empty')
        + "\nSubject: " + subject
        + "\nArchive path: s3://" + bucket_name + '/' + message_id
    )

    # The file name to use for the attached message. Uses regex to remove all
    # non-alphanumeric characters, and appends a file extension.
    filename = re.sub('[^0-9a-zA-Z]+', '_', subject) + ".eml"
    
    # Create a MIME container.
    msg = MIMEMultipart()
    # Create a MIME text part.
    text_part = MIMEText(body_text, _subtype='plain')
    # Attach the text part to the MIME message.
    msg.attach(text_part)

    # Add subject, from and to lines.
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # Create a new MIME object message/rfc822.
    attachment = MIMEBase('message', 'rfc822')
    attachment.set_payload(file)
    email.encoders.encode_base64(attachment)
 
    attachment.add_header('Content-Disposition', 'attachment',
                            filename = filename)
    msg.attach(attachment)
    
    message = {
        'Source': sender,
        'Destinations': recipient,
        'Data': msg.as_string()
    }

    return message

def send_email(message):

    # Create a new SES client.
    client_ses = boto3.client('ses', region)

    # Send the email.
    try:
        # Provide the contents of the email.
        response = client_ses.send_raw_email(
            Source=message['Source'],
            Destinations=[
                message['Destinations']
            ],
            RawMessage={
                'Data':message['Data']
            }
        )

    # Display an error if something goes wrong.
    except ClientError as e:
        output = e.response['Error']['Message']
    else:
        output = 'E-mail sent with message_id: ' + response['MessageId']

    return output

def lambda_handler(event, context):
    # Get the unique ID of the message. This corresponds to the name of the file
    # in S3.
    message_id = event['Records'][0]['ses']['mail']['messageId']
    
    print(f"message_id {message_id}")
    print(f"bucket_name: {bucket_name}")
    
    # Retrieve the file from the S3 bucket.
    file = get_message_from_s3(message_id)

    # Create the message.
    message = create_message(message_id, file)

    # Send the email and print the result.
    result = send_email(message)
    print(result)
