#!/usr/bin/env python
"""Test API compression endpoint"""
import asyncio
import json
from pathlib import Path
from PIL import Image
import tempfile
import httpx

# Create a test image
test_dir = Path(tempfile.gettempdir()) / "test_api_compression"
test_dir.mkdir(exist_ok=True)

test_image_path = test_dir / "test.jpg"
img = Image.new('RGB', (800, 600), color='blue')
img.save(test_image_path)

async def test_compression():
    """Test the compression API"""
    async with httpx.AsyncClient() as client:
        # 1. Test service status
        print("1. Testing service status...")
        resp = await client.get("http://localhost:8000/api/v1/image/status")
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        
        # 2. Test compression
        print("\n2. Testing image compression...")
        with open(test_image_path, 'rb') as f:
            files = {'file': ('test.jpg', f, 'image/jpeg')}
            data = {
                'options': json.dumps({
                    'quality': 85,
                    'max_width': 1920,
                    'max_height': 1080
                })
            }
            
            resp = await client.post(
                "http://localhost:8000/api/v1/image/compress",
                files=files,
                data=data
            )
            
            print(f"   Status: {resp.status_code}")
            result = resp.json()
            print(f"   Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if resp.status_code == 200:
                # 3. Try to download the result
                print("\n3. Testing download...")
                task_id = result.get('filename', '').split('_')[0] if result.get('filename') else 'unknown'
                
                # Extract task_id from download_url
                download_url = result.get('download_url', '')
                if download_url:
                    download_url = f"http://localhost:8000{download_url}" if not download_url.startswith('http') else download_url
                    print(f"   Download URL: {download_url}")
                    
                    download_resp = await client.get(download_url)
                    print(f"   Download Status: {download_resp.status_code}")
                    print(f"   Content-Type: {download_resp.headers.get('content-type')}")
                    print(f"   Content-Length: {len(download_resp.content)}")

# Run test
if __name__ == "__main__":
    try:
        asyncio.run(test_compression())
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        test_image_path.unlink(missing_ok=True)
        test_dir.rmdir()
        print("\nTest complete!")
