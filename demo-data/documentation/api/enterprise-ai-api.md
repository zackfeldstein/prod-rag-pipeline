# Enterprise AI Platform API Documentation

## Overview

The Enterprise AI Platform provides RESTful APIs for integrating AI capabilities into your applications. Our APIs support natural language processing, computer vision, predictive analytics, and automated decision-making.

## Authentication

All API requests require authentication using API keys. Include your API key in the Authorization header:

```
Authorization: Bearer YOUR_API_KEY
```

### Obtaining API Keys

1. Sign up for an account at https://platform.enterpriseai.com
2. Navigate to API Keys in your dashboard
3. Generate a new API key for your application
4. Store the key securely (it cannot be retrieved again)

## Base URL

```
https://api.enterpriseai.com/v1
```

## Rate Limits

- Free tier: 1,000 requests per month
- Starter: 10,000 requests per month  
- Professional: 100,000 requests per month
- Enterprise: Custom limits

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Your rate limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when limits reset

## Endpoints

### Natural Language Processing

#### POST /nlp/analyze
Analyze text for sentiment, entities, topics, and more.

**Request Body:**
```json
{
  "text": "The new product launch exceeded our expectations with 150% growth in Q4.",
  "features": ["sentiment", "entities", "topics", "keywords"],
  "language": "en"
}
```

**Response:**
```json
{
  "sentiment": {
    "label": "positive",
    "confidence": 0.94
  },
  "entities": [
    {
      "text": "Q4",
      "label": "TIME_PERIOD",
      "confidence": 0.98
    }
  ],
  "topics": ["business", "growth", "product"],
  "keywords": ["product launch", "growth", "expectations"],
  "processing_time_ms": 45
}
```

#### POST /nlp/summarize
Generate summaries of long text documents.

**Request Body:**
```json
{
  "text": "Long document text here...",
  "max_length": 200,
  "style": "abstractive"
}
```

### Computer Vision

#### POST /vision/analyze
Analyze images for objects, scenes, text, and more.

**Request:** Multipart form with image file

**Response:**
```json
{
  "objects": [
    {
      "label": "person",
      "confidence": 0.96,
      "bounding_box": [100, 150, 200, 300]
    }
  ],
  "scene": "office",
  "text_detected": "Company Logo",
  "colors": ["blue", "white", "gray"]
}
```

### Predictive Analytics

#### POST /analytics/predict
Make predictions based on historical data.

**Request Body:**
```json
{
  "model_id": "sales_forecast_v2",
  "features": {
    "historical_sales": [1000, 1200, 1100, 1300],
    "marketing_spend": 5000,
    "season": "Q4",
    "region": "North America"
  },
  "prediction_horizon": 30
}
```

**Response:**
```json
{
  "prediction": 1450,
  "confidence_interval": [1380, 1520],
  "confidence": 0.89,
  "model_version": "2.1.0",
  "factors": [
    {
      "feature": "marketing_spend",
      "importance": 0.35
    }
  ]
}
```

### Decision Automation

#### POST /decisions/evaluate
Automated decision-making for business rules.

**Request Body:**
```json
{
  "decision_model": "loan_approval",
  "inputs": {
    "credit_score": 750,
    "income": 75000,
    "debt_ratio": 0.3,
    "employment_years": 5
  }
}
```

**Response:**
```json
{
  "decision": "approved",
  "confidence": 0.91,
  "explanation": [
    "High credit score (750) indicates low risk",
    "Stable employment history",
    "Low debt-to-income ratio"
  ],
  "recommended_amount": 250000,
  "conditions": ["standard_terms"]
}
```

## Error Handling

The API uses standard HTTP status codes:

- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid API key)
- `403` - Forbidden (insufficient permissions)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

Error responses include detailed information:

```json
{
  "error": {
    "code": "invalid_parameter",
    "message": "The 'text' parameter is required",
    "details": {
      "parameter": "text",
      "expected_type": "string"
    }
  },
  "request_id": "req_123456789"
}
```

## SDKs and Libraries

Official SDKs are available for:

- Python: `pip install enterpriseai-python`
- JavaScript/Node.js: `npm install enterpriseai-js`
- Java: Maven/Gradle packages available
- .NET: NuGet package available

### Python Example

```python
from enterpriseai import Client

client = Client(api_key="your_api_key")

# Analyze sentiment
result = client.nlp.analyze(
    text="I love this new feature!",
    features=["sentiment"]
)

print(result.sentiment.label)  # "positive"
```

### JavaScript Example

```javascript
const { Client } = require('enterpriseai-js');

const client = new Client('your_api_key');

// Make prediction
const prediction = await client.analytics.predict({
  model_id: 'sales_forecast_v2',
  features: {
    historical_sales: [1000, 1200, 1100],
    marketing_spend: 5000
  }
});

console.log(prediction.prediction);
```

## Webhooks

Configure webhooks to receive real-time notifications for long-running operations.

### Webhook Configuration

```json
{
  "url": "https://your-app.com/webhooks/ai-results",
  "events": ["prediction.completed", "analysis.failed"],
  "secret": "your_webhook_secret"
}
```

### Webhook Payload

```json
{
  "event": "prediction.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "request_id": "req_123456789",
    "result": {
      "prediction": 1450,
      "confidence": 0.89
    }
  }
}
```

## Best Practices

1. **Cache Results**: Cache API responses when appropriate to reduce costs
2. **Batch Requests**: Use batch endpoints for processing multiple items
3. **Error Handling**: Implement robust error handling and retries
4. **Rate Limiting**: Respect rate limits and implement backoff strategies
5. **Security**: Never expose API keys in client-side code

## Support

- Documentation: https://docs.enterpriseai.com
- Community Forum: https://community.enterpriseai.com
- Email Support: support@enterpriseai.com (Enterprise customers)
- Status Page: https://status.enterpriseai.com
