# ATH ERP Credentials

## App Login
- Set up via signup page — no default credentials

## Integration Notes

### Razorpay
- Add live Key ID and Secret to backend `.env`
- Test cards: 4111 1111 1111 1111 (any future expiry, any CVV)

### Twilio
- Add Account SID, Auth Token, and phone numbers to backend `.env`
- WhatsApp sandbox: recipient must send join code to the sandbox number first

### ElevenLabs
- Add API key and Voice ID to backend `.env`
- Free tier blocks library voices via API — upgrade to Starter plan or clone a voice in Voice Lab

### Cloudinary
- Add Cloud Name, API Key, and API Secret to backend `.env`
- Uploads go to folder `ath-erp/<tenant_id>/products/`
