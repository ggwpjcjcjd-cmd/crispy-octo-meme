"""One authenticated public-demo generation, using only a verified free account."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1'
os.environ['GRADIO_ANALYTICS_ENABLED']='False'
from gradio_client import Client,handle_file
from huggingface_hub import HfApi

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--clip-id',required=True)
    ap.add_argument('--image',required=True,type=Path)
    ap.add_argument('--prompt',required=True,type=Path)
    ap.add_argument('--duration',required=True,type=float)
    ap.add_argument('--width',default=1152,type=int)
    ap.add_argument('--height',default=640,type=int)
    ap.add_argument('--seed',default=20261027,type=int)
    args=ap.parse_args()
    if not args.clip_id.replace('_','').replace('-','').isalnum():ap.error('Invalid clip id')
    if not 1<=args.duration<=10:ap.error('Duration must be 1–10 seconds')
    if args.width%64 or args.height%64:ap.error('Dimensions must be multiples of 64')
    assert args.image.is_file() and args.prompt.is_file()
    out=ROOT.parent/'motion_sources'/args.clip_id
    out.mkdir(parents=True,exist_ok=True)
    destination=out/'clip.mp4'
    if destination.is_file():
        qa_path=out/'qa.json'
        if qa_path.is_file() and json.loads(qa_path.read_text()).get('approved') is False:
            raise RuntimeError('This take was rejected semantically. Generate a separately named take; do not silently reuse or overwrite it.')
        print('Existing completed clip retained:',destination,flush=True);return
    if (out/'request.json').exists():
        raise RuntimeError('A request already exists. Diagnose it; no automatic resubmission.')
    token=os.environ.get('HF_TOKEN')
    if not token:raise RuntimeError('HF_TOKEN is not present; no request submitted.')
    request=urllib.request.Request('https://huggingface.co/api/whoami-v2',headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(request,timeout=20) as response:profile=json.load(response)
    if profile.get('type')!='user' or profile.get('isPro') is not False:
        raise RuntimeError('Free personal account not confirmed; paid GPU use is not authorized.')
    quota=HfApi(token=token).get_zero_gpu_quota()
    # Verified deployed spaces 0.50.4 auto-selects xlarge for these model weights:
    # fixed duration 75 seconds reserves 2 * 75 seconds of the free quota.
    if quota.remaining < 150:
        raise RuntimeError(f'Insufficient free GPU allocation quota: {quota.remaining:.1f}s left; '
                           f'this demo reserves 150s. Reset UTC: {quota.resets_at.isoformat()}')
    client=Client('Lightricks/LTX-2-3',token=token,max_workers=1,analytics_enabled=False,
                  download_files=out,httpx_kwargs={'timeout':60})
    prompt=args.prompt.read_text(encoding='utf-8').strip()
    metadata={'clip_id':args.clip_id,'provider':'Lightricks/LTX-2-3','source':str(args.image),
              'source_sha256':hashlib.sha256(args.image.read_bytes()).hexdigest(),
              'prompt':prompt,'duration':args.duration,'width':args.width,'height':args.height,
              'seed':args.seed,'enhance_prompt':False,'account_is_free':True}
    metadata['free_quota_before']={'base':quota.base,'remaining':quota.remaining,
                                 'resets_at_utc':quota.resets_at.isoformat(),
                                 'reservation_seconds':150}
    (out/'request.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False))
    print('Submitting one generation:',args.clip_id,flush=True)
    started=time.monotonic()
    try:
        job=client.submit(input_image=handle_file(str(args.image)),prompt=prompt,
             duration=args.duration,enhance_prompt=False,seed=args.seed,randomize_seed=False,
             height=args.height,width=args.width,api_name='/generate_video')
        last=None
        while not job.done():
            code=str(job.status().code)
            if code!=last:
                print(f'{args.clip_id}: {code}, wall {time.monotonic()-started:.1f}s',flush=True);last=code
            if time.monotonic()-started>420:
                raise TimeoutError('Existing job exceeds seven minutes; do not resubmit.')
            time.sleep(2)
        result=job.result()
        if not isinstance(result,(list,tuple)) or not result or not result[0]:
            raise RuntimeError('Provider returned no video.')
        source=Path(result[0]);assert source.is_file()
        shutil.copy2(source,destination)
        summary={'path':str(destination),'bytes':destination.stat().st_size,
          'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
          'elapsed_wall_seconds':time.monotonic()-started,'provider_result':result}
        (out/'result.json').write_text(json.dumps(summary,indent=2,default=str))
        print('COMPLETED:',json.dumps({k:v for k,v in summary.items() if k!='provider_result'}),flush=True)
    except Exception as error:
        report={'error_type':type(error).__name__,'message':str(error),'elapsed_wall_seconds':time.monotonic()-started}
        (out/'error.json').write_text(json.dumps(report,indent=2))
        raise
    finally:client.close()

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(type(error).__name__+': '+str(error),flush=True)
        raise SystemExit(2)
