#!/usr/bin/env python3
"""Validate a structured delivery manifest. Does not claim to verify semantic accuracy or pixel-perfect layout."""
import json, argparse, sys
from pathlib import Path
from collections import Counter
from PIL import Image

RULES={'min_pages':3,'width':1242,'height':1656}
FATAL={'PAGE_COUNT','BAD_DIMENSION','MISSING_IMAGE','REPEATED_INGREDIENT','MISSING_ANSWER','RECIPE_PAGE_COUNT','RECIPE_STEPS','RECIPE_ASSET','TITLE_LENGTH','MISSING_BODY','MISSING_QUERY'}

def run(manifest):
    data=json.loads(manifest.read_text(encoding='utf-8'))
    root=manifest.parent
    problems=[]
    def bad(code,msg,page=None):problems.append({'code':code,'message':msg,'page':page,'severity':'blocking' if code in FATAL else 'review'})
    query=data.get('query','').strip(); typ=data.get('type',''); pages=data.get('pages',[])
    if not query:bad('MISSING_QUERY','缺少原始 query')
    if len(pages)<3:bad('PAGE_COUNT','图文必须至少3页')
    if not data.get('direct_answer','').strip():bad('MISSING_ANSWER','缺少针对原问题的直接回答')
    if not data.get('body','').strip():bad('MISSING_BODY','缺少图文配套正文')
    if len(data.get('title',''))>=20:bad('TITLE_LENGTH','标题须少于20字')
    if not data.get('template_id'):bad('TEMPLATE_UNAPPROVED','需记录客户验收的 template_id')
    if not data.get('template_approved',False):bad('TEMPLATE_UNAPPROVED','模板须先经客户批准')
    if typ=='介绍' and len([p for p in pages if p.get('role')=='recipe'])!=3:bad('RECIPE_PAGE_COUNT','介绍类必须有三张食谱页')
    ids=[]
    for i,p in enumerate(pages,1):
        target=(root/p.get('file','')).resolve()
        if not target.is_relative_to(root) or not target.is_file():bad('MISSING_IMAGE',f'找不到第{i}页文件',i);continue
        try:
            with Image.open(target) as img:
                if img.size!=(1242,1656):bad('BAD_DIMENSION',f'第{i}页尺寸{img.size}，须1242x1656',i)
        except Exception as exc:bad('MISSING_IMAGE',f'图像无法读取: {exc}',i)
        if not p.get('layout_reviewed',False):bad('LAYOUT_NOT_REVIEWED','需要核对坐标遮挡、错字、排版',i)
        if not p.get('content_reviewed',False):bad('CONTENT_NOT_REVIEWED','需要人工审核内容是否真正回答问题',i)
        ids += [str(x).strip().lower() for x in p.get('new_ingredient_ids',[]) if str(x).strip()]
        if p.get('role')=='recipe':
            if not p.get('recipe_title','').strip() or len(p.get('steps',[]))<2:bad('RECIPE_STEPS','食谱缺少菜名或至少两步明确操作',i)
            if p.get('asset_kind') not in {'licensed_real_step_photos','owned_real_step_photos'}:bad('RECIPE_ASSET','食谱图必须为具有使用许可的真实操作步骤图片',i)
            if not p.get('recipe_matches_query',False):bad('CONTENT_NOT_REVIEWED','未确认食谱与原始问题相关',i)
    if typ in {'推荐','盘点'}:
        dup=[k for k,v in Counter(ids).items() if v>1]
        if dup:bad('REPEATED_INGREDIENT','详情食材重复: '+','.join(dup))
        if ids and data.get('ingredient_order') and ids!=[str(x).strip().lower() for x in data['ingredient_order']]:bad('ORDER_MISMATCH','详情食材顺序与声明顺序不一致')
    if not data.get('sources_verified',False):bad('FACTS_NOT_VERIFIED','营养数值与健康说法仍需逐条核实')
    if not data.get('asset_rights_verified',False):bad('RIGHTS_NOT_VERIFIED','素材使用权未确认')
    return problems

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('--report',type=Path)
    args=ap.parse_args(); problems=run(args.manifest)
    result={'status':'FAIL' if any(x['severity']=='blocking' for x in problems) else ('REVIEW' if problems else 'PASS'),'issues':problems}
    out=json.dumps(result,ensure_ascii=False,indent=2);print(out)
    if args.report:args.report.write_text(out,encoding='utf-8')
    sys.exit(1 if result['status']=='FAIL' else 0)
