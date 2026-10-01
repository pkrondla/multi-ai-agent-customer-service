import azure.cognitiveservices.speech as speechsdk
from azure.ai.vision.imageanalysis.models import VisualFeatures


class AzureAIService:
    def __init__(self, vision_client, speech_config, doc_intel_client):
        """Initialize service wrapper with Azure clients.

        Parameters:
        - vision_client: client for Azure Vision
        - speech_config: configuration object for Azure Speech SDK
        - doc_intel_client: client for Azure Document Intelligence
        """
        self.vision_client = vision_client
        self.speech_config = speech_config
        self.doc_intel_client = doc_intel_client

    def analyze_image(self, image_path):
        """
        Azure AI Vision - Analyzes an image file.

        Returns:
        1. A caption describing the image (if supported in the region)
        2. Any text found in the image (OCR)
        3. Tags describing objects in the image

        The agent can't see images directly - it calls this service and gets text back.
        """
        if not self.vision_client:
            return "ERROR: Vision service is not configured."

        print(f"[VISION] Analyzing image: {image_path}")

        # Read the image file as binary data
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
        except FileNotFoundError:
            return f"ERROR: Image file not found at '{image_path}'"
        except Exception as error:
            return f"ERROR reading image file: {error}"

        try:
            # Call Vision API with two features: Caption and Read (OCR)
            result = self.vision_client.analyze(
                image_data=image_data,
                visual_features=[
                    VisualFeatures.READ,
                    # VisualFeatures.CAPTION, // Not available for all regions
                    VisualFeatures.TAGS,
                ],  # Features include: VisualFeatures.CAPTION, VisualFeatures.READ, VisualFeatures.OBJECTS, VisualFeatures.BRANDS, VisualFeatures.CATEGORIES, VisualFeatures.COLOR, VisualFeatures.FACES, VisualFeatures.TAGS
                language="en",
            )

            response_parts = []

            # Get the image caption (description of what's in the image)
            if result.caption:
                caption_text = result.caption.text
                caption_confidence = result.caption.confidence
                response_parts.append(
                    f"Image description: {caption_text} "
                    f"(confidence: {caption_confidence:.2f})"
                )
            else:
                response_parts.append("No caption generated for this image.")

            # Extract text from the image using OCR
            if result.read and result.read.blocks:
                ocr_texts = []
                for block in result.read.blocks:
                    for line in block.lines:
                        ocr_texts.append(line.text)
                if ocr_texts:
                    response_parts.append(f"Text found in image: {' '.join(ocr_texts)}")
                else:
                    response_parts.append("No text found in this image.")
            else:
                response_parts.append("No text found in this image.")

            # Extract tags from the image
            if not result.tags or len(result.tags) == 0:
                response_parts.append("No tags detected in this image.")
            else:
                tags_info = []
                tags_extract = result.tags["values"]

                for tag in tags_extract:
                    tags_info.append(f"{tag.name} (confidence: {tag.confidence:.2f})")
                response_parts.append(f"Tags detected: {', '.join(tags_info)}")

            return "\n".join(response_parts)

        except Exception as error:
            print(f"[VISION] Error: {error}")
            return f"ERROR analyzing image: {error}"

    def speech_to_text(self, audio_file_path):
        """
        Azure AI Speech - Converts spoken audio to text.

        Takes an audio file path (WAV, MP3, etc.) and returns the transcribed text.
        The agent can't hear audio directly - it calls this tool and gets text back.
        """
        if not self.speech_config:
            return "ERROR: Speech service is not configured."

        print(f"[SPEECH] Converting speech to text from: {audio_file_path}")

        try:
            # Create audio config pointing to the audio file
            audio_config = speechsdk.AudioConfig(filename=audio_file_path)

            # Create speech recognizer with the configuration
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, audio_config=audio_config
            )

            # Perform recognition (convert speech to text)
            result = recognizer.recognize_once()

            # Check the result status
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                print(f"[SPEECH] Recognized: {result.text}")
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                return "No speech could be recognized from the audio file."
            else:
                return f"Speech recognition failed: {result.reason}"

        except Exception as error:
            print(f"[SPEECH] Error: {error}")
            return f"ERROR converting speech to text: {error}"

    def analyze_document(self, file_path, document_type="invoice"):
        """
        Azure AI Document Intelligence - Extracts structured data from documents.

        Supported document types:
        - invoice: extracts vendor, customer, total amount, date
        - receipt: extracts merchant, total, date
        - id: extracts name, date of birth, document number

        The agent can't read PDFs directly - it calls this tool to get structured data.
        """
        if not self.doc_intel_client:
            return "ERROR: Document Intelligence service is not configured."

        # Prebuilt model mapping (provided by Azure - no training needed)
        model_mapping = {
            "invoice": "prebuilt-invoice",
            "receipt": "prebuilt-receipt",
            "id": "prebuilt-idDocument",
        }

        model_id = model_mapping.get(document_type, "prebuilt-invoice")
        print(f"[DOC_INTEL] Analyzing {document_type} from: {file_path}")

        try:
            with open(file_path, "rb") as f:
                document_data = f.read()
        except FileNotFoundError:
            return f"ERROR: Document file not found at '{file_path}'"
        except Exception as error:
            return f"ERROR reading document file: {error}"

        try:
            # Call Document Intelligence API to analyze the document
            poller = self.doc_intel_client.begin_analyze_document(
                model_id=model_id,
                body=document_data,
            )
            result = poller.result()

            if not result.documents:
                return f"No {document_type} data found in the document."

            document = result.documents[0]
            fields = document.fields

            # Extract relevant fields based on document type
            extracted_data = []

            if document_type == "invoice":
                if fields.get("VendorName"):
                    extracted_data.append(
                        f"Vendor: {fields['VendorName'].value_string}"
                    )
                if fields.get("CustomerName"):
                    extracted_data.append(
                        f"Customer: {fields['CustomerName'].value_string}"
                    )
                if fields.get("InvoiceTotal"):
                    amount = fields["InvoiceTotal"].value_currency
                    extracted_data.append(
                        f"Total: {amount.amount} {amount.currency_code}"
                    )
                if fields.get("InvoiceDate"):
                    extracted_data.append(f"Date: {fields['InvoiceDate'].value_date}")

            elif document_type == "receipt":
                if fields.get("MerchantName"):
                    extracted_data.append(
                        f"Merchant: {fields['MerchantName'].value_string}"
                    )
                if fields.get("Total"):
                    amount = fields["Total"].value_currency
                    extracted_data.append(
                        f"Total: {amount.amount} {amount.currency_code}"
                    )
                if fields.get("TransactionDate"):
                    extracted_data.append(
                        f"Date: {fields['TransactionDate'].value_date}"
                    )

            elif document_type == "id":
                if fields.get("FirstName"):
                    extracted_data.append(
                        f"First Name: {fields['FirstName'].value_string}"
                    )
                if fields.get("LastName"):
                    extracted_data.append(
                        f"Last Name: {fields['LastName'].value_string}"
                    )
                if fields.get("DateOfBirth"):
                    extracted_data.append(
                        f"Date of Birth: {fields['DateOfBirth'].value_date}"
                    )
                if fields.get("DocumentNumber"):
                    extracted_data.append(
                        f"Document Number: {fields['DocumentNumber'].value_string}"
                    )

            if extracted_data:
                return f"Extracted {document_type} data:\n" + "\n".join(extracted_data)
            else:
                return (
                    f"Document analyzed but no standard {document_type} fields found."
                )

        except Exception as error:
            print(f"[DOC_INTEL] Error: {error}")
            return f"ERROR analyzing document: {error}"

    def route_multimodal_request(self, content_type, content_path):
        """
        Route the user's request to the appropriate multimodal tool.

        The agent examines the content_type (image, audio, document) and calls
        the correct Azure AI service. Each service returns text that the LLM can use.
        """
        content_type_lower = content_type.lower()

        if content_type_lower in ["image", "jpg", "jpeg", "png", "gif", "bmp"]:
            return self.analyze_image(content_path)

        elif content_type_lower in ["audio", "mp3", "wav", "m4a", "flac"]:
            return self.speech_to_text(content_path)

        elif content_type_lower in ["document", "invoice", "receipt", "pdf", "id"]:
            doc_type = "invoice"
            if "receipt" in content_type_lower:
                doc_type = "receipt"
            elif "id" in content_type_lower:
                doc_type = "id"
            return self.analyze_document(content_path, doc_type)

        else:
            return (
                f"ERROR: Unknown content type '{content_type}'. "
                f"Supported types: image, audio, document"
            )
