from odoo import models, fields, api
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import openai
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    customer_segment = fields.Selection([
        ('A', 'Segment A - High Value'),
        ('B', 'Segment B - Medium Value'),
        ('C', 'Segment C - Low Value')
    ], string='Customer Segment', tracking=True)
    
    deal_score = fields.Float(
        string='Deal Score (%)',
        help='AI predicted probability of winning the deal',
        tracking=True
    )
    
    ai_next_action = fields.Text(
        string='AI Recommended Action',
        help='Next best action recommended by AI'
    )
    
    last_ai_update = fields.Datetime(
        string='Last AI Update',
        help='Last time AI analysis was performed'
    )

    gift_status = fields.Selection([
        ('pending', 'Chưa tặng quà'),
        ('suggested', 'Đã đề xuất quà'),
        ('sent', 'Đã gửi quà'),
        ('declined', 'Từ chối quà')
    ], string='Trạng thái quà tặng', default='pending', tracking=True)
    
    suggested_gift = fields.Text(
        string='Quà tặng đề xuất',
        help='Quà tặng được AI đề xuất cho khách hàng'
    )
    
    gift_value = fields.Float(
        string='Giá trị quà tặng',
        help='Giá trị ước tính của quà tặng'
    )
    
    gift_sent_date = fields.Date(
        string='Ngày gửi quà',
        help='Ngày quà tặng được gửi cho khách hàng'
    )

    def action_run_ai_analysis(self):
        """Manual trigger for AI analysis"""
        self._run_ai_analysis()
        return True

    def _run_ai_analysis(self):
        """Main method to run AI analysis"""
        try:
            # 1. Customer Segmentation
            self._perform_customer_segmentation()
            
            # 2. Lead Scoring
            self._predict_lead_score()
            
            # 3. Next Best Action
            self._generate_next_action()
            
            # Add gift suggestion for won opportunities
            won_leads = self.filtered(lambda l: l.probability == 100 and l.gift_status == 'pending')
            if won_leads:
                won_leads._generate_gift_suggestion()
            
            # Update timestamp
            self.last_ai_update = fields.Datetime.now()
            
        except Exception as e:
            _logger.error(f"AI Analysis failed: {str(e)}")
            raise

    def _perform_customer_segmentation(self):
        """Perform customer segmentation using K-means clustering"""
        # Get relevant data for clustering
        leads = self.search([
            ('type', '=', 'opportunity'),
            ('customer_segment', '!=', False)
        ])
        
        if not leads:
            return
            
        # Prepare features for clustering
        features = pd.DataFrame({
            'expected_revenue': leads.mapped('expected_revenue'),
            'probability': leads.mapped('probability'),
            'create_date': leads.mapped('create_date')
        })
        
        # Scale features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)
        
        # Perform clustering
        kmeans = KMeans(n_clusters=3, random_state=42)
        clusters = kmeans.fit_predict(scaled_features)
        
        # Map clusters to segments
        segment_map = {0: 'C', 1: 'B', 2: 'A'}
        for lead, cluster in zip(leads, clusters):
            lead.customer_segment = segment_map[cluster]

    def _predict_lead_score(self):
        """Predict lead score using historical data"""
        # Simple scoring based on probability and expected revenue
        for lead in self:
            base_score = lead.probability
            revenue_factor = min(lead.expected_revenue / 10000, 1)  # Normalize revenue
            lead.deal_score = (base_score * 0.7 + revenue_factor * 0.3) * 100

    def _generate_next_action(self):
        """Generate next best action using OpenAI API"""
        for lead in self:
            # Prepare context for OpenAI
            context = f"""
            Lead: {lead.name}
            Customer: {lead.partner_id.name if lead.partner_id else 'Unknown'}
            Stage: {lead.stage_id.name}
            Probability: {lead.probability}%
            Expected Revenue: {lead.expected_revenue}
            Last Activity: {lead.activity_date_deadline}
            """
            
            try:
                # Call OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a CRM assistant that suggests next best actions for sales leads."},
                        {"role": "user", "content": f"Based on this lead information, what should be the next best action?\n{context}"}
                    ]
                )
                
                lead.ai_next_action = response.choices[0].message.content
                
            except Exception as e:
                _logger.error(f"OpenAI API call failed: {str(e)}")
                lead.ai_next_action = "Error generating recommendation"

    def _generate_gift_suggestion(self):
        """Generate gift suggestion using OpenAI API"""
        for lead in self:
            if not lead.expected_revenue or lead.gift_status != 'pending':
                continue
                
            # Tính toán giá trị quà tặng dựa trên doanh thu
            gift_value = min(lead.expected_revenue * 0.05, 1000000)  # 5% doanh thu, tối đa 1 triệu
            
            # Chuẩn bị context cho OpenAI
            context = f"""
            Thông tin khách hàng:
            - Tên: {lead.partner_id.name if lead.partner_id else 'Unknown'}
            - Doanh thu dự kiến: {lead.expected_revenue:,.0f} VND
            - Giá trị quà tặng tối đa: {gift_value:,.0f} VND
            - Ngành nghề: {lead.partner_id.industry_id.name if lead.partner_id and lead.partner_id.industry_id else 'Unknown'}
            - Loại khách hàng: {lead.customer_segment}
            
            Hãy đề xuất 3 món quà phù hợp với khách hàng này, bao gồm:
            1. Món quà chính (giá trị khoảng {gift_value * 0.7:,.0f} VND)
            2. Món quà phụ (giá trị khoảng {gift_value * 0.3:,.0f} VND)
            3. Lý do chọn quà
            
            Format đề xuất:
            - Quà chính: [tên quà] - [giá trị] - [lý do]
            - Quà phụ: [tên quà] - [giá trị] - [lý do]
            """
            
            try:
                # Gọi OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Bạn là trợ lý bán hàng chuyên nghiệp, giúp đề xuất quà tặng phù hợp cho khách hàng."},
                        {"role": "user", "content": context}
                    ]
                )
                
                lead.suggested_gift = response.choices[0].message.content
                lead.gift_value = gift_value
                lead.gift_status = 'suggested'
                
            except Exception as e:
                _logger.error(f"OpenAI API call failed for gift suggestion: {str(e)}")
                lead.suggested_gift = "Lỗi khi tạo đề xuất quà tặng"

    def action_suggest_gift(self):
        """Manual trigger for gift suggestion"""
        self._generate_gift_suggestion()
        return True

    def action_mark_gift_sent(self):
        """Mark gift as sent"""
        self.write({
            'gift_status': 'sent',
            'gift_sent_date': fields.Date.today()
        })
        return True

    def action_decline_gift(self):
        """Mark gift as declined"""
        self.write({
            'gift_status': 'declined',
            'suggested_gift': False,
            'gift_value': 0
        })
        return True 