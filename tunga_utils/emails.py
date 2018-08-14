import re

from django.core.mail.message import EmailMultiAlternatives
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from premailer import premailer

from tunga.settings import DEFAULT_FROM_EMAIL, EMAIL_SUBJECT_PREFIX
from tunga_utils.helpers import convert_to_text
from tunga_utils.hubspot_utils import create_hubspot_engagement


def render_mail(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    """
    :param subject:
    :param template_prefix: path to template for email with extension (e.g hello if template name is hello.html)
    :param to_emails:
    :param context: variables to be passed into template
    :param bcc:
    :param cc:
    :param kwargs:
    :return:
    """
    from_email = DEFAULT_FROM_EMAIL
    if not re.match(r'^\[\s*Tunga', subject):
        subject = '{} {}'.format(EMAIL_SUBJECT_PREFIX, subject)

    bodies = {}
    for ext in ['html', 'txt']:
        try:
            template_name = '{0}.{1}'.format(template_prefix, ext)
            bodies[ext] = render_to_string(template_name,
                                           context).strip()
        except TemplateDoesNotExist:
            if ext == 'txt':
                if 'html' in bodies:
                    # Compose text body from html
                    bodies[ext] = convert_to_text(bodies['html'])
                else:
                    # We need at least one body
                    raise

    if bodies:
        msg = EmailMultiAlternatives(subject, bodies['txt'], from_email, to_emails, bcc=bcc, cc=cc)
        if 'html' in bodies:
            try:
                html_body = render_to_string(
                    'tunga/email/base.html', dict(email_content=bodies['html'])
                ).strip()
            except TemplateDoesNotExist:
                html_body = bodies['html']
            msg.attach_alternative(premailer.transform(html_body), 'text/html')
    else:
        raise TemplateDoesNotExist
    return msg


def send_mail(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    msg = render_mail(subject, template_prefix, to_emails, context, bcc=bcc, cc=cc, **kwargs)
    is_sent = msg.send()
    if is_sent:
        # Log engagement in HubSpot
        new_kwargs = kwargs
        new_kwargs.update(
            dict(cc=cc, bcc=bcc, context=context, template_prefix=template_prefix)
        )
        try:
            create_hubspot_engagement(
                from_email=msg.from_email, to_emails=msg.to, subject=msg.subject, body=msg.body, **kwargs
            )
        except:
            pass
    return is_sent
