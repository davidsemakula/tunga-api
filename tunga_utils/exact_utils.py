import base64
from decimal import Decimal

from six.moves.urllib_parse import urlencode

from exactonline.api import ExactApi
from exactonline.exceptions import ObjectDoesNotExist
from exactonline.resource import POST, GET
from exactonline.storage import ExactOnlineConfig

from tunga.settings import EXACT_DOCUMENT_TYPE_PURCHASE_INVOICE, \
    EXACT_DOCUMENT_TYPE_SALES_INVOICE, \
    EXACT_JOURNAL_CLIENT_SALES, EXACT_JOURNAL_DEVELOPER_SALES, \
    EXACT_JOURNAL_DEVELOPER_PURCHASE, \
    EXACT_PAYMENT_CONDITION_CODE_14_DAYS, EXACT_VAT_CODE_NL, \
    EXACT_VAT_CODE_WORLD, EXACT_GL_ACCOUNT_CLIENT_FEE, \
    EXACT_GL_ACCOUNT_DEVELOPER_FEE, EXACT_GL_ACCOUNT_TUNGA_FEE, \
    EXACT_VAT_CODE_EUROPE, EXACT_GL_ACCOUNT_NEW_DEVELOPER_FEE
from tunga_utils.constants import CURRENCY_EUR, VAT_LOCATION_NL, \
    VAT_LOCATION_EUROPE, INVOICE_TYPE_SALE, \
    INVOICE_TYPE_PURCHASE, PROJECT_CATEGORY_PROJECT, PROJECT_CATEGORY_DEDICATED
from tunga_utils.models import SiteMeta


class ExactStorage(ExactOnlineConfig):

    def get_meta_key(self, section, option):
        return 'exact.{}.{}'.format(section, option)

    def get(self, section, option):
        try:
            return SiteMeta.objects.get(meta_key=self.get_meta_key(section, option)).meta_value
        except:
            return None

    def set(self, section, option, value):
        SiteMeta.objects.update_or_create(meta_key=self.get_meta_key(section, option), defaults=dict(meta_value=value))


def get_api():
    storage = ExactStorage()
    return ExactApi(storage=storage)


def get_account_guid(user, invoice_type, exact_api=None):
    if not exact_api:
        exact_api = get_api()

    exact_user_id = None
    try:
        exact_user_id = exact_api.relations.get(relation_code=user.exact_code)['ID']
    except (ObjectDoesNotExist, TypeError):
        pass

    relation_dict = dict(
        Code=user.exact_code,
        Name=user.display_name,
        Email=user.email,
        City=user.profile and user.profile.city_name or '',
        Country=user.profile and user.profile.country.code or '',
    )

    if invoice_type in ['client', 'developer']:
        relation_dict['Status'] = 'C'  # Is customer with no status

    relation_dict['IsSales'] = False
    relation_dict['IsSupplier'] = bool(invoice_type != 'client')

    if exact_user_id:
        exact_api.relations.update(exact_user_id, relation_dict)
    else:
        exact_user = exact_api.relations.create(relation_dict)
        exact_user_id = exact_user['ID']
    return exact_user_id


def get_entry(invoice_type, invoice_number, exact_user_id, exact_api=None):
    if not exact_api:
        exact_api = get_api()

    existing_invoice_refs = None
    select_param = "EntryID,EntryNumber,EntryDate,Created,Modified,YourRef," \
                   "AmountDC,VATAmountDC,DueDate,Description,Journal,ReportingYear"

    if invoice_type in ['client', 'developer']:
        existing_invoice_refs = exact_api.restv1(GET(
            "salesentry/SalesEntries?{}".format(urlencode({
                '$filter': "YourRef eq '{}' and Customer eq guid'{}'".format(invoice_number, exact_user_id),
                '$select': '{},SalesEntryLines,Customer'.format(select_param)
            }))
        ))
    elif invoice_type == 'tunga':
        existing_invoice_refs = exact_api.restv1(GET(
            "purchaseentry/PurchaseEntries?{}".format(urlencode({
                '$filter': "YourRef eq '{}' and Supplier eq guid'{}'".format(invoice_number, exact_user_id),
                '$select': '{},PurchaseEntryLines,Supplier'.format(select_param)
            }))
        ))
    return existing_invoice_refs


def upload_invoice(task, user, invoice_type, invoice_file, amount, vat_location=None):
    """
    :param task: parent task for the invoice
    :param user: Tunga user related to the invoice e.g a client or a developer
    :param invoice_type: type of invoice e.g 'client', 'developer', 'tunga'
    :param invoice_file: generated file object for the invoice
    :param amount:
    :param vat_location: NL, europe or world
    :return:
    """
    exact_api = get_api()
    invoice = task.invoice

    if invoice_type == 'developer' and invoice.version > 1:
        # Developer (tunga invoicing dev) invoices are only part of the old invoice scheme
        return

    invoice_number = invoice.invoice_id(invoice_type=invoice_type, user=user)

    exact_user_id = get_account_guid(user, invoice_type, exact_api=exact_api)

    existing_invoice_refs = get_entry(invoice_type, invoice_number, exact_user_id, exact_api=exact_api)

    if existing_invoice_refs:
        # Stop if entries with invoice ref already exist
        return

    exact_document = exact_api.restv1(POST(
        'documents/Documents',
        dict(
            Type=invoice_type == 'tunga' and EXACT_DOCUMENT_TYPE_PURCHASE_INVOICE or EXACT_DOCUMENT_TYPE_SALES_INVOICE,
            Subject='{} - {}'.format(
                invoice.title,
                invoice_number
            ),
            Account=exact_user_id,
        )
    ))

    exact_api.restv1(POST(
        'documents/DocumentAttachments',
        dict(
            Attachment=base64.b64encode(invoice_file),
            Document=exact_document['ID'],
            FileName='{} - {}.pdf'.format(invoice.title, invoice_number)
        )
    ))

    if invoice_type == 'client':
        vat_code = EXACT_VAT_CODE_WORLD
        if vat_location == VAT_LOCATION_NL:
            vat_code = EXACT_VAT_CODE_NL
        elif vat_location == VAT_LOCATION_EUROPE:
            vat_code = EXACT_VAT_CODE_EUROPE
        exact_api.restv1(POST(
            'salesentry/SalesEntries',
            dict(
                Currency=CURRENCY_EUR,
                Customer=exact_user_id,
                Description=task.summary,
                Document=exact_document['ID'],
                EntryDate=invoice.created_at.isoformat(),
                Journal=EXACT_JOURNAL_CLIENT_SALES,
                ReportingPeriod=invoice.created_at.month,
                ReportingYear=invoice.created_at.year,
                YourRef=invoice_number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                SalesEntryLines=[
                    dict(
                        AmountFC=amount,
                        Description=invoice_number,
                        GLAccount=EXACT_GL_ACCOUNT_CLIENT_FEE,
                        VATCode=vat_code
                    )
                ]
            )
        ))
    elif invoice_type == 'tunga':
        exact_api.restv1(POST(
            'purchaseentry/PurchaseEntries',
            dict(
                Currency=CURRENCY_EUR,
                Supplier=exact_user_id,
                Description=task.summary,
                Document=exact_document['ID'],
                EntryDate=invoice.created_at.isoformat(),
                Journal=EXACT_JOURNAL_DEVELOPER_PURCHASE,
                ReportingPeriod=invoice.created_at.month,
                ReportingYear=invoice.created_at.year,
                YourRef=invoice_number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                PurchaseEntryLines=[
                    dict(
                        AmountFC=amount,
                        Description=invoice_number,
                        GLAccount=EXACT_GL_ACCOUNT_DEVELOPER_FEE
                    )
                ]
            )
        ))
    elif invoice_type == 'developer':
        exact_api.restv1(POST(
            'salesentry/SalesEntries',
            dict(
                Currency=CURRENCY_EUR,
                Customer=exact_user_id,
                Description=task.summary,
                Document=exact_document['ID'],
                EntryDate=invoice.created_at.isoformat(),
                Journal=EXACT_JOURNAL_DEVELOPER_SALES,
                ReportingPeriod=invoice.created_at.month,
                ReportingYear=invoice.created_at.year,
                YourRef=invoice_number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                SalesEntryLines=[
                    dict(
                        AmountFC=amount,
                        Description=invoice_number,
                        GLAccount=EXACT_GL_ACCOUNT_TUNGA_FEE
                    )
                ]
            )
        ))


def get_account_guid_v3(user, invoice_type=None, exact_api=None):
    if not exact_api:
        exact_api = get_api()

    exact_user_id = None
    try:
        exact_user_id = exact_api.relations.get(relation_code=user.exact_code)['ID']
    except (ObjectDoesNotExist, TypeError):
        pass

    profile_source = user.is_project_owner and user.company or user.profile
    account_name = user.display_name

    if user.is_project_owner:
        if user.company and user.company.name:
            account_name = user.company.name
        elif user.profile and user.profile.company:
            account_name = user.profile.company

    relation_dict = dict(
        Code=user.exact_code,
        Name=account_name,
        Email=user.email,
        City=profile_source and profile_source.city_name or '',
        Country=profile_source and profile_source.country.code or '',
    )

    if invoice_type in INVOICE_TYPE_SALE:
        relation_dict['Status'] = 'C'  # Is customer with no status

    relation_dict['IsSales'] = False
    relation_dict['IsSupplier'] = bool(invoice_type != INVOICE_TYPE_SALE)

    if exact_user_id:
        exact_api.relations.update(exact_user_id, relation_dict)
    else:
        exact_user = exact_api.relations.create(relation_dict)
        exact_user_id = exact_user['ID']
    return exact_user_id


def get_entry_v3(invoice, exact_user_id, exact_api=None):
    if not exact_api:
        exact_api = get_api()

    existing_invoice_refs = None
    select_param = "EntryID,EntryNumber,EntryDate,Created,Modified,YourRef," \
                   "AmountDC,VATAmountDC,DueDate,Description,Journal,ReportingYear"

    if invoice.type == INVOICE_TYPE_SALE:
        existing_invoice_refs = exact_api.restv1(GET(
            "salesentry/SalesEntries?{}".format(urlencode({
                '$filter': "YourRef eq '{}' and Customer eq guid'{}'".format(invoice.number, exact_user_id),
                '$select': '{},SalesEntryLines,Customer'.format(select_param)
            }))
        ))
    elif invoice.type == INVOICE_TYPE_PURCHASE:
        existing_invoice_refs = exact_api.restv1(GET(
            "purchaseentry/PurchaseEntries?{}".format(urlencode({
                '$filter': "YourRef eq '{}' and Supplier eq guid'{}'".format(invoice.number, exact_user_id),
                '$select': '{},PurchaseEntryLines,Supplier'.format(select_param)
            }))
        ))
    return existing_invoice_refs


def upload_invoice_v3(invoice):
    """
    :param invoice:
    :return:
    """
    exact_api = get_api()

    if invoice.legacy_id or invoice.user.email in ['david@tunga.io', 'bart@tunga.io', 'domieck@tunga.io']:
        # Don't sync legacy and admin invoices
        return

    exact_user_id = get_account_guid_v3(invoice.user, invoice_type=invoice.type, exact_api=exact_api)

    existing_invoice_refs = get_entry_v3(invoice, exact_user_id, exact_api=exact_api)

    if existing_invoice_refs:
        # Stop if entries with invoice ref already exist
        return

    exact_document = exact_api.restv1(POST(
        'documents/Documents',
        dict(
            Type=invoice.type == INVOICE_TYPE_PURCHASE and EXACT_DOCUMENT_TYPE_PURCHASE_INVOICE or EXACT_DOCUMENT_TYPE_SALES_INVOICE,
            Subject='{} - {}'.format(
                invoice.full_title,
                invoice.number
            ),
            Account=exact_user_id,
        )
    ))

    exact_api.restv1(POST(
        'documents/DocumentAttachments',
        dict(
            Attachment=base64.b64encode(invoice.pdf),
            Document=exact_document['ID'],
            FileName='{} - {}.pdf'.format(invoice.full_title, invoice.number).replace(':', '__')
        )
    ))

    if invoice.type == INVOICE_TYPE_SALE:
        vat_location = invoice.tax_location
        vat_code = EXACT_VAT_CODE_WORLD
        if vat_location == VAT_LOCATION_NL:
            vat_code = EXACT_VAT_CODE_NL
        elif vat_location == VAT_LOCATION_EUROPE:
            vat_code = EXACT_VAT_CODE_EUROPE

        sales_entry_lines = [
            dict(
                AmountFC=float(invoice.subtotal),
                Description=invoice.number,
                GLAccount=EXACT_GL_ACCOUNT_CLIENT_FEE,
                VATCode=vat_code
            )
        ]

        margin_amount = Decimal(0)
        if invoice.project.category == PROJECT_CATEGORY_PROJECT:
            margin_amount = Decimal('0.4') * invoice.subtotal
        elif invoice.project.category == PROJECT_CATEGORY_DEDICATED:
            margin_amount = Decimal('0.5') * invoice.subtotal

        if margin_amount > Decimal(0):
            sales_entry_lines.append(
                dict(
                    AmountFC=float(margin_amount),
                    Description=invoice.number,
                    GLAccount=EXACT_GL_ACCOUNT_NEW_DEVELOPER_FEE
                )
            )
            sales_entry_lines.append(
                dict(
                    AmountFC=float(margin_amount*Decimal(-1)),
                    Description=invoice.number,
                    GLAccount=EXACT_GL_ACCOUNT_DEVELOPER_FEE
                )
            )

        exact_api.restv1(POST(
            'salesentry/SalesEntries',
            dict(
                Currency=CURRENCY_EUR,
                Customer=exact_user_id,
                Description=invoice.full_title,
                Document=exact_document['ID'],
                EntryDate=invoice.issued_at.isoformat(),
                Journal=EXACT_JOURNAL_CLIENT_SALES,
                ReportingPeriod=invoice.issued_at.month,
                ReportingYear=invoice.issued_at.year,
                YourRef=invoice.number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                SalesEntryLines=sales_entry_lines
            )
        ))

    elif invoice.type == INVOICE_TYPE_PURCHASE:
        exact_api.restv1(POST(
            'purchaseentry/PurchaseEntries',
            dict(
                Currency=CURRENCY_EUR,
                Supplier=exact_user_id,
                Description=invoice.full_title,
                Document=exact_document['ID'],
                EntryDate=invoice.issued_at.isoformat(),
                Journal=EXACT_JOURNAL_DEVELOPER_PURCHASE,
                ReportingPeriod=invoice.issued_at.month,
                ReportingYear=invoice.issued_at.year,
                YourRef=invoice.number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                PurchaseEntryLines=[
                    dict(
                        AmountFC=float(invoice.subtotal),
                        Description=invoice.number,
                        GLAccount=invoice.project.category and EXACT_GL_ACCOUNT_NEW_DEVELOPER_FEE or EXACT_GL_ACCOUNT_DEVELOPER_FEE
                    )
                ]
            )
        ))


def get_project_entry_v3(entry_ref, exact_user_id, exact_api=None):
    if not exact_api:
        exact_api = get_api()

    select_param = "EntryID,EntryNumber,EntryDate,Created,Modified,YourRef," \
                   "AmountDC,VATAmountDC,DueDate,Description,Journal,ReportingYear"

    existing_project_entry_refs = exact_api.restv1(GET(
        "salesentry/SalesEntries?{}".format(urlencode({
            '$filter': "YourRef eq '{}' and Customer eq guid'{}'".format(
                entry_ref, exact_user_id),
            '$select': '{},SalesEntryLines,Customer'.format(select_param)
        }))
    ))
    return existing_project_entry_refs


def create_project_entry_v3(project, balance):
    """
    :param project:
    :param balance:
    :return:
    """
    exact_api = get_api()

    if balance == Decimal(0) or not project.archived:
        # Nothing to add to Exact yet
        return

    if project.legacy_id or not project.category:
        # Don't sync legacy projects
        return

    project_owner = project.owner or project.user
    project_ref = 'P/{}'.format(project.id)

    exact_user_id = get_account_guid_v3(project_owner, invoice_type=INVOICE_TYPE_SALE, exact_api=exact_api)

    existing_project_entry_refs = get_project_entry_v3(project_ref, exact_user_id, exact_api=exact_api)

    if existing_project_entry_refs:
        # Stop if entries with invoice ref already exist
        return

    sales_entry_lines = [
        dict(
            AmountFC=float(balance),
            Description=project_ref,
            GLAccount=EXACT_GL_ACCOUNT_NEW_DEVELOPER_FEE
        ),
        dict(
            AmountFC=float(balance * Decimal(-1)),
            Description=project_ref,
            GLAccount=EXACT_GL_ACCOUNT_DEVELOPER_FEE
        )
    ]

    exact_api.restv1(POST(
        'salesentry/SalesEntries',
        dict(
            Currency=CURRENCY_EUR,
            Customer=exact_user_id,
            Description=project.title,
            EntryDate=project.created_at.isoformat(),
            Journal=EXACT_JOURNAL_CLIENT_SALES,
            ReportingPeriod=project.created_at.month,
            ReportingYear=project.created_at.year,
            YourRef=project_ref,
            PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
            SalesEntryLines=sales_entry_lines
        )
    ))
