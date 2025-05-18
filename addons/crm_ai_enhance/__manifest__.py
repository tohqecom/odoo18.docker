{
    'name': 'CRM AI Enhancement',
    'version': '1.0',
    'category': 'Sales/CRM',
    'summary': 'AI-powered CRM enhancements for lead scoring and customer segmentation',
    'description': """
        This module enhances Odoo CRM with AI/ML capabilities:
        * Automatic Customer Segmentation
        * Lead Scoring Prediction
        * Next Best Action Recommendations
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['crm', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/crm_lead_views.xml',
        'views/crm_ai_report_views.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 