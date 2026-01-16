#!/usr/bin/env python3
"""
Runpod Serverless Endpoint Test Script for Clothes Swap - Flux Fill +Redux+automask
This script sends a request to your deployed Runpod serverless endpoint using the testinput_outfitswap.json file.
"""

import requests
import json
import time
import os
import sys
import base64
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

class RunpodTester:
    def __init__(self, api_key: str, endpoint_id: str):
        """
        Initialize the Runpod tester.
        
        Args:
            api_key: Your Runpod API key
            endpoint_id: Your serverless endpoint ID
        """
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        self.base_url = "https://api.runpod.ai/v2"
        
    def load_test_input(self, json_file_path: str) -> Dict[str, Any]:
        """Load the test input JSON file."""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Error: Test input file not found: {json_file_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in test input file: {e}")
            sys.exit(1)
    
    def send_sync_request(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a synchronous request to the Runpod endpoint.
        
        Args:
            input_data: The input data to send
            
        Returns:
            Response from the endpoint
        """
        url = f"{self.base_url}/{self.endpoint_id}/runsync"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🚀 Sending synchronous request to: {url}")
        print(f"📊 Request size: {len(json.dumps(input_data))} characters")
        
        try:
            response = requests.post(url, json=input_data, headers=headers, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            print("⏰ Request timed out after 5 minutes")
            return {"error": "timeout"}
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            return {"error": str(e)}
    
    def send_async_request(self, input_data: Dict[str, Any]) -> str:
        """
        Send an asynchronous request to the Runpod endpoint.
        
        Args:
            input_data: The input data to send
            
        Returns:
            Job ID for status checking
        """
        url = f"{self.base_url}/{self.endpoint_id}/run"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🚀 Sending asynchronous request to: {url}")
        print(f"📊 Request size: {len(json.dumps(input_data))} characters")
        
        try:
            response = requests.post(url, json=input_data, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result.get("id", "")
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            return ""
    
    def check_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Check the status of an asynchronous job.
        
        Args:
            job_id: The job ID to check
            
        Returns:
            Job status and result
        """
        url = f"{self.base_url}/{self.endpoint_id}/status/{job_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Status check failed: {e}")
            return {"error": str(e)}
    
    def wait_for_completion(self, job_id: str, max_wait_time: int = 600) -> Dict[str, Any]:
        """
        Wait for an asynchronous job to complete.
        
        Args:
            job_id: The job ID to wait for
            max_wait_time: Maximum wait time in seconds (default: 10 minutes)
            
        Returns:
            Final job result
        """
        print(f"⏳ Waiting for job {job_id} to complete...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_result = self.check_job_status(job_id)
            
            if "error" in status_result:
                return status_result
            
            status = status_result.get("status", "UNKNOWN")
            print(f"📋 Job status: {status}")
            
            if status in ["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"]:
                return status_result
            
            time.sleep(10)  # Wait 10 seconds before checking again
        
        print(f"⏰ Job timed out after {max_wait_time} seconds")
        return {"error": "timeout", "message": f"Job did not complete within {max_wait_time} seconds"}
    
    def decode_base64_image(self, base64_string: str, output_path: str) -> bool:
        """
        Decode a base64 image string and save it as an image file.
        
        Args:
            base64_string: The base64 encoded image string
            output_path: Path where to save the decoded image
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove data URL prefix if present (e.g., "data:image/png;base64,")
            if base64_string.startswith('data:'):
                base64_string = base64_string.split(',', 1)[1]
            
            # Decode the base64 string
            image_data = base64.b64decode(base64_string)
            
            # Write the image data to file
            with open(output_path, 'wb') as f:
                f.write(image_data)
            
            print(f"🖼️  Image saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to decode/save image: {e}")
            return False
    
    def process_result_images(self, result: Dict[str, Any], output_dir: Path, timestamp: int) -> List[str]:
        """
        Process and save all base64 images from the result.
        
        Args:
            result: The API response result
            output_dir: Directory to save images
            timestamp: Timestamp for unique filenames
            
        Returns:
            List of saved image file paths
        """
        saved_images = []
        
        try:
            # Check if result has output with images
            output = result.get('output', {})
            images = output.get('images', [])
            
            if not images:
                print("ℹ️  No images found in the result")
                return saved_images
            
            print(f"🖼️  Found {len(images)} image(s) to process")
            
            for i, image_data in enumerate(images):
                if isinstance(image_data, dict):
                    # Extract image info
                    filename = image_data.get('filename', f'image_{i+1}.png')
                    image_type = image_data.get('type', '')
                    image_content = image_data.get('data', '') or image_data.get('image', '')
                    
                    if image_type == 'base64' and image_content:
                        # Create unique filename with timestamp
                        name_part, ext = os.path.splitext(filename)
                        unique_filename = f"{name_part}_{timestamp}{ext}"
                        output_path = output_dir / unique_filename
                        
                        # Decode and save the image
                        if self.decode_base64_image(image_content, str(output_path)):
                            saved_images.append(str(output_path))
                    else:
                        content_length = len(image_content) if image_content else 0
                        print(f"⚠️  Skipping image {i+1}: type='{image_type}', content_length={content_length}")
                        
            print(f"✅ Successfully processed {len(saved_images)} image(s)")
            
        except Exception as e:
            print(f"❌ Error processing images: {e}")
        
        return saved_images
    
    def process_swap_results(self, result: Dict[str, Any], output_dir: Path, timestamp: int) -> None:
        """
        Process and save clothes swap specific results (masks, intermediate steps, etc.).
        
        Args:
            result: The API response result
            output_dir: Directory to save results
            timestamp: Timestamp for unique filenames
        """
        try:
            output = result.get('output', {})
            
            # Look for mask data or other swap-specific outputs
            mask_data = None
            if 'masks' in output:
                mask_data = output['masks']
            elif 'mask' in output:
                mask_data = output['mask']
            elif 'segmentation' in output:
                mask_data = output['segmentation']
            
            if mask_data:
                # Save mask results as JSON
                mask_file = output_dir / f"mask_results_{timestamp}.json"
                with open(mask_file, 'w', encoding='utf-8') as f:
                    json.dump(mask_data, f, indent=2, ensure_ascii=False)
                print(f"🎭 Mask results saved to: {mask_file}")
            
            # Look for intermediate processing steps
            intermediate_data = None
            if 'intermediate' in output:
                intermediate_data = output['intermediate']
            elif 'steps' in output:
                intermediate_data = output['steps']
            
            if intermediate_data:
                # Save intermediate results as JSON
                intermediate_file = output_dir / f"intermediate_results_{timestamp}.json"
                with open(intermediate_file, 'w', encoding='utf-8') as f:
                    json.dump(intermediate_data, f, indent=2, ensure_ascii=False)
                print(f"⚙️  Intermediate results saved to: {intermediate_file}")
            
        except Exception as e:
            print(f"❌ Error processing swap results: {e}")
    
    def save_result(self, result: Dict[str, Any], output_file: str) -> None:
        """Save the result to a JSON file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Result saved to: {output_file}")
        except Exception as e:
            print(f"❌ Failed to save result: {e}")

def main():
    """Main function to run the test."""
    print("🧪 Runpod Clothes Swap - Flux Fill +Redux+automask Endpoint Tester")
    print("=" * 70)
    
    # Get credentials from environment variables or user input
    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    
    if not api_key:
        api_key = input("🔑 Enter your Runpod API key: ").strip()
    
    if not endpoint_id:
        endpoint_id = input("🎯 Enter your endpoint ID: ").strip()
    
    if not api_key or not endpoint_id:
        print("❌ Error: API key and endpoint ID are required")
        sys.exit(1)
    
    # Configuration
    test_input_file = Path(__file__).parent / "testinput_outfitswap_test_sam.json"
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    # Initialize tester
    tester = RunpodTester(api_key, endpoint_id)
    
    # Load test input
    print(f"📂 Loading test input from: {test_input_file}")
    input_data = tester.load_test_input(str(test_input_file))
    
    # Choose request type
    print("\n🔄 Choose request type:")
    print("1. Synchronous (runsync) - Wait for immediate result")
    print("2. Asynchronous (run) - Get job ID and check status")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    timestamp = int(time.time())
    
    if choice == "1":
        # Synchronous request
        print("\n⚡ Running synchronous test...")
        result = tester.send_sync_request(input_data)
        
        # Save result
        output_file = output_dir / f"sync_result_{timestamp}.json"
        tester.save_result(result, str(output_file))
        
        # Display result summary
        if "error" not in result:
            print(f"✅ Request completed successfully!")
            print(f"⏱️  Execution time: {result.get('executionTime', 'N/A')} ms")
            print(f"⏳ Delay time: {result.get('delayTime', 'N/A')} ms")
            print(f"📊 Status: {result.get('status', 'N/A')}")
            
            # Process and save images from result
            print("\n🎨 Processing result images...")
            saved_images = tester.process_result_images(result, output_dir, timestamp)
            if saved_images:
                print(f"🖼️  Saved {len(saved_images)} image(s):")
                for img_path in saved_images:
                    print(f"   📁 {img_path}")
            
            # Process clothes swap specific results
            print("\n👗 Processing clothes swap results...")
            tester.process_swap_results(result, output_dir, timestamp)
        else:
            print(f"❌ Request failed: {result.get('error', 'Unknown error')}")
    
    elif choice == "2":
        # Asynchronous request
        print("\n🔄 Running asynchronous test...")
        job_id = tester.send_async_request(input_data)
        
        if job_id:
            print(f"✅ Job submitted successfully! Job ID: {job_id}")
            
            # Wait for completion
            result = tester.wait_for_completion(job_id)
            
            # Save result
            output_file = output_dir / f"async_result_{timestamp}.json"
            tester.save_result(result, str(output_file))
            
            # Display result summary
            if "error" not in result:
                print(f"✅ Job completed successfully!")
                print(f"⏱️  Execution time: {result.get('executionTime', 'N/A')} ms")
                print(f"⏳ Delay time: {result.get('delayTime', 'N/A')} ms")
                print(f"📊 Status: {result.get('status', 'N/A')}")
                
                # Process and save images from result
                print("\n🎨 Processing result images...")
                saved_images = tester.process_result_images(result, output_dir, timestamp)
                if saved_images:
                    print(f"🖼️  Saved {len(saved_images)} image(s):")
                    for img_path in saved_images:
                        print(f"   📁 {img_path}")
                
                # Process clothes swap specific results
                print("\n👗 Processing clothes swap results...")
                tester.process_swap_results(result, output_dir, timestamp)
            else:
                print(f"❌ Job failed: {result.get('error', 'Unknown error')}")
        else:
            print("❌ Failed to submit job")
    
    else:
        print("❌ Invalid choice")
        sys.exit(1)
    
    print("\n🏁 Test completed!")

if __name__ == "__main__":
    main()
