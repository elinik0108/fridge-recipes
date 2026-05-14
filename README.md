# Fridge Recipe AI

An intelligent application that scans your fridge, detects food items using AI vision, and generates personalized recipes based on what's available. Built with  cloud infrastructure and by YOLOv8 object detection and Google Gemini AI.

## Features

- **Smart Food Detection**: Uses YOLOv8 neural network to identify food items from fridge photos
- **AI Recipe Generation**: Uses Google Gemini API to generate recipes based on detected ingredients
- **Cloud Storage**: Secure image storage and management with AWS S3
- **Scan History**: Tracks all scans in AWS DynamoDB for future reference
- **Presigned URLs**: Secure, temporary upload links for image uploads
- **UI**: React + Vite frontend
- **Serverless Inference**: Lambda-compatible inference handler for scalable deployment
- **Infrastructure as Code**: Complete Terraform configuration for AWS deployment


## Prerequisites

- Python 3.8+
- Node.js 16+
- AWS Account with:
  - S3 bucket access
  - DynamoDB access
  - Lambda permissions
- Google API key (for Gemini)
- Git



### Backend Setup

1. **Clone and navigate to project**:
   ```bash
   cd /path/to/fridge
   ```

2. **Create Python virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install backend dependencies**:
   ```bash
   pip install -r app/requirements.txt
   pip install -r inference/requirements.txt
   ```

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```


### Environment Variables

Create a `.env` file in the `app/` directory:

```env
# AWS Configuration
AWS_REGION=eu-north-1
AWS_ACCOUNT=123456789012
UPLOAD_BUCKET=fridge-uploads-{AWS_ACCOUNT}
DYNAMO_TABLE=fridge-scans

# Google Gemini API
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-2.5-flash

# Optional
USER_ID=local
PRESIGN_EXPIRY=300
```

### Lambda Inference Configuration

For the inference Lambda function, set these environment variables:

```env
MODEL_PATH=/var/task/yolov8n.onnx
CONF_THRESHOLD=0.25
IOU_THRESHOLD=0.45
DYNAMO_TABLE=fridge-scans
```

## Usage

### Local Development

1. **Start Backend**:
   ```bash
   cd app
   source ../.venv/bin/activate
   uvicorn main:app --reload --port 8000
   ```

2. **Start Frontend** (in another terminal):
   ```bash
   cd frontend
   npm run dev
   ```

   Frontend will be available at `http://localhost:5173`

### API Endpoints

#### Get Presigned Upload URL
```bash
GET /presign
Response:
{
  "scan_id": "scan-uuid",
  "upload_url": "https://s3.amazonaws.com/...",
  "method": "PUT",
  "expires_in": 300
}
```


## Deployment

### Infrastructure as Code (Terraform)

Navigate to the `terraform/` directory to deploy to AWS:

```bash
cd terraform

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply configuration
terraform apply
```

This will provision:
- S3 bucket for image uploads
- DynamoDB table for scan storage
- Lambda function for inference
- API Gateway endpoints
- IAM roles and policies

### Docker Deployment

Build and run using Docker:

```bash
# Backend
docker build -f Dockerfile -t fridge-backend .
docker run -e GEMINI_API_KEY=your-key fridge-backend

# Inference
docker build -f inference/Dockerfile -t fridge-inference .
docker run fridge-inference
```

## Object Detection

The YOLOv8n model can detect 80 different food items including:

- **Fruits**: apple, banana, orange, etc.
- **Vegetables**: broccoli, carrot, etc.
- **Proteins**: chicken, fish, etc.
- **Dairy**: milk, cheese, etc.
- **Pantry**: rice, pasta, bread, etc.

For a complete list, see [inference/class_names.json](inference/class_names.json).

## Performance Considerations

- **Model**: YOLOv8n (nano) - optimized for speed and low memory
- **Input Size**: 640×640 pixels
- **Confidence Threshold**: 0.25 (adjustable)
- **IOU Threshold**: 0.45 (adjustable)
- **Inference Time**: ~50-100ms on CPU

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### ONNX Runtime Issues
```bash
pip install --upgrade onnxruntime
```

### Missing AWS Credentials
Ensure AWS credentials are configured:
```bash
aws configure
# or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
```

### Gemini API Errors
Verify your API key is valid and has appropriate permissions at [Google AI Studio](https://aistudio.google.com).



---
