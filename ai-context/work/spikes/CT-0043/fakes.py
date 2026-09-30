"""The fake RunPod the tests use: the editor returns a picture, the video endpoint a clip."""
import base64, io, os
from pathlib import Path
from cine_toaster import jobs, spend

class Fake:
    def __init__(self):
        from PIL import Image
        buffer = io.BytesIO(); Image.new("RGB", (1280, 704), "blue").save(buffer, "PNG")
        self.picture = buffer.getvalue()
        self.video = Path(os.environ["SPIKE_CLIP"]).read_bytes()
        self.log = Path(os.environ["SPIKE_LOG"])
    def __call__(self, path, body):
        endpoint = path.split("/")[1]
        if path.endswith("/run"):
            with self.log.open("a") as handle: handle.write(endpoint + "\n")
            return {"id": f"{endpoint}-x", "status": "IN_QUEUE"}
        output = ({"image": base64.b64encode(self.picture).decode()} if endpoint == "editor"
                  else {"videos": [base64.b64encode(self.video).decode()]})
        return {"status": "COMPLETED", "delayTime": 500, "executionTime": 2000, "output": output}

def install():
    os.environ.update(RUNPOD_QWEN_ENDPOINT_ID="editor", RUNPOD_LTX_ENDPOINT_ID="video")
    jobs.GENERATION_TRANSPORT = Fake()
    spend.set_limit(2)
