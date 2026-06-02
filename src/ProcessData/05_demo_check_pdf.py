"""
05_demo_check_pdf.py - Demo phat hien dao van (Realtime)
Chay tren: Colab (GPU)
"""
import hashlib, random
import os, re, time, pickle, unicodedata
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.fs as pafs

BUCKET = "bigdata-n9-ptit-final"
SHINGLE_K = 5
NUM_PERM = 128
FUZZY_THRESHOLD = 0.85
SEMANTIC_THRESHOLD = 0.85

gcs = pafs.GcsFileSystem()

# =================================================================
# LOAD DU LIEU (1 lan)
# =================================================================
print("[1/4] Load metadata...")
t0 = time.time()
df_meta = pq.read_table("bigdata-n9-ptit-final/silver/arxiv_silver_plus", filesystem=gcs,
    columns=["paper_id", "title", "authors", "categories"]).to_pandas()
meta_dict = {row["paper_id"]: row.to_dict() for _, row in df_meta.iterrows()}
print("  {} bai".format(len(meta_dict)))

def pid_to_url(pid):
    base = re.sub(r'v\d+$', '', pid.replace("arxiv_", "").replace(".pdf", ""))
    return "https://arxiv.org/abs/{}".format(base)

print("[2/4] Load FAISS...")
os.makedirs("/tmp/faiss", exist_ok=True)
if not os.path.exists("/tmp/faiss/faiss_index.bin"):
    os.system("gsutil cp gs://{}/intermediate/faiss_index/faiss_index.bin /tmp/faiss/faiss_index.bin".format(BUCKET))
import faiss
faiss_index = faiss.read_index("/tmp/faiss/faiss_index.bin")
df_faiss_meta = pq.read_table("bigdata-n9-ptit-final/intermediate/faiss_index/chunk_metadata.parquet",
    filesystem=gcs).to_pandas()
print("  {} vectors".format(faiss_index.ntotal))

print("[3/4] Load MinHash LSH...")
os.makedirs("/tmp/minhash", exist_ok=True)
for f in ["lsh_index.pkl", "minhashes.pkl"]:
    if not os.path.exists("/tmp/minhash/" + f):
        os.system("gsutil cp gs://{}/intermediate/minhash_index/{} /tmp/minhash/".format(BUCKET, f))
with open("/tmp/minhash/lsh_index.pkl", "rb") as f: lsh_index = pickle.load(f)
with open("/tmp/minhash/minhashes.pkl", "rb") as f: minhashes_dict = pickle.load(f)
print("  {} papers".format(len(minhashes_dict)))

print("[4/4] Load model...")
import torch
from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained("allenai/specter")
emb_model = AutoModel.from_pretrained("allenai/specter")
device = "cuda" if torch.cuda.is_available() else "cpu"
emb_model = emb_model.to(device).eval()
print("  Device: {}".format(device))

try:
    from Levenshtein import ratio as lev_ratio
except ImportError:
    from difflib import SequenceMatcher
    def lev_ratio(s1, s2): return SequenceMatcher(None, s1, s2).ratio()

print("San sang! {:.0f}s\n".format(time.time() - t0))

# =================================================================
# TIEN XU LY (DONG BO VOI 02_clean_text.py)
# =================================================================
import fitz
from datasketch import MinHash


def extract_text_from_pdf(fp):
    doc = fitz.open(fp)
    text = "\n".join(p.get_text() for p in doc).strip()
    doc.close()
    return text

def clean_text(text):
    """9 tang lam sach - DONG BO voi 02_clean_text.py"""
    if not text: return ""
    t = text
    # Tang 1: ArXiv header
    t = re.sub(r'^arXiv:\S+\s+\[[\w.\-]+\]\s+\d+\s+\w+\s+\d{4}\s*\n', '', t, flags=re.MULTILINE)
    # Tang 2: Journal metadata
    t = re.sub(
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|'
        r'Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+\d{1,2},?\s+\d{4}\n\d{1,2}:\d{2}\n', '', t)
    t = re.sub(
        r'(?:WSPC|World Scientific|Typeset with|Preprint submitted to|'
        r'Preprint typeset using|Draft version)[^\n]*\n(?:[^\n]{0,60}\n){0,2}', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^[A-Z]{2,10}-[\w/\-]+(?:,\s*[A-Z]{2,10}-[\w/\-]+)*\s*\n', '', t, flags=re.MULTILINE)
    # Tang 3: References (chi 40% cuoi)
    total_len = len(t)
    ss = int(total_len * 0.60)
    rm = re.search(r'\n\s*(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*\n', t[ss:])
    if rm: t = t[:ss + rm.start()]
    else:
        ss2 = int(total_len * 0.75)
        rm2 = re.search(r'\n(?:\[\d+\]|\d+[\)\.]\s)\s*[A-Z][^.]{15,}\n(?:(?:\[\d+\]|\d+[\)\.]\s)\s*.{10,}\n){4,}', t[ss2:])
        if rm2: t = t[:ss2 + rm2.start()]
    # Tang 4: So trang
    t = re.sub(r'\n\s*\d{1,3}\s*\n', '\n', t)
    t = re.sub(r'\n\s*\d+/\d+\s*\n', '\n', t)
    t = re.sub(r'\bpage\s+\d+\s+of\s+\d+\b', '', t, flags=re.IGNORECASE)
    # Tang 5: Ligatures
    for lig, rep in {'\ufb00':'ff','\ufb01':'fi','\ufb02':'fl',
                     '\ufb03':'ffi','\ufb04':'ffl','\ufb05':'st','\ufb06':'st'}.items():
        t = t.replace(lig, rep)
    # Tang 6: Unicode NFKC
    t = unicodedata.normalize("NFKC", t)
    # Tang 7: Ky tu khong in
    t = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', t)
    # Tang 8: Hyphenation
    t = re.sub(r'(\w)-\n(\w)', r'\1\2', t)
    # Tang 9: Email, URL, whitespace
    t = re.sub(r'\[?\w+@[\w.]+\]?\(?mailto:[\w@.]+\)?', '', t)
    t = re.sub(r'\S+@\S+\.\S+', '', t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t.strip()

def extract_abstract(text):
    m = re.search(r'(?:abstract|ABSTRACT)\s*[:\.]?\s*\n?(.*?)(?:\n\s*(?:1\.?\s*|I\.?\s*)?'
                  r'(?:Introduction|INTRODUCTION|Keywords|KEYWORDS))', text, re.DOTALL|re.IGNORECASE)
    if m and len(m.group(1).strip()) > 50: return m.group(1).strip()
    m2 = re.search(r'(?:abstract|ABSTRACT)\s*[:\.]?\s*\n?(.{100,2000})', text, re.DOTALL|re.IGNORECASE)
    if m2: return m2.group(1).strip()
    return " ".join(text.split()[:300])

def split_sentences(text):
    if not text or len(str(text)) < 30: return []
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', str(text).strip()) if len(s.strip()) >= 30]

def embed_text(text):
    inputs = tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
    with torch.no_grad(): out = emb_model(**inputs)
    emb = out.last_hidden_state[:, 0, :].cpu().numpy().astype(np.float32)
    faiss.normalize_L2(emb)
    return emb

random.seed(42)
LARGE_PRIME = 2147483647
HASH_A = [random.randint(1, LARGE_PRIME - 1) for _ in range(NUM_PERM)]
HASH_B = [random.randint(0, LARGE_PRIME - 1) for _ in range(NUM_PERM)]

def text_to_minhash(text):
    """Tao MinHash CUNG hash params voi 04b_minhash_signatures.py"""
    words = re.findall(r'\w{2,}', text.lower())
    if len(words) < SHINGLE_K: return None

    # Hash shingles
    shingle_hashes = set()
    for i in range(len(words) - SHINGLE_K + 1):
        s = " ".join(words[i:i+SHINGLE_K])
        h = int(hashlib.md5(s.encode()).hexdigest(), 16) % LARGE_PRIME
        shingle_hashes.add(h)

    if not shingle_hashes: return None

    sig = []
    for i in range(NUM_PERM):
        a, b = HASH_A[i], HASH_B[i]
        min_val = LARGE_PRIME
        for h in shingle_hashes:
            val = (a * h + b) % LARGE_PRIME
            if val < min_val: min_val = val
        sig.append(min_val)

    # Dat vao datasketch MinHash object
    m = MinHash(num_perm=NUM_PERM)
    m.hashvalues = np.array(sig, dtype=np.uint64)
    return m

# =================================================================
# 5 LAYERS
# =================================================================
def layer1_minhash(query_mh):
    if query_mh is None: return 0.0, {}
    candidates = lsh_index.query(query_mh)
    results = {}
    for pid in candidates:
        if pid in minhashes_dict:
            sim = query_mh.jaccard(minhashes_dict[pid])
            if sim >= 0.3: results[pid] = {"jaccard": round(sim, 4)}
    return round(max((v["jaccard"] for v in results.values()), default=0.0), 4), results

def layer2_fuzzy(query_sents, candidate_pids):
    pid_list = list(candidate_pids)
    try:
        df_text = pq.read_table("bigdata-n9-ptit-final/silver/arxiv_silver_plus", filesystem=gcs,
            columns=["paper_id","abstract","introduction","body"],
            filters=[("paper_id","in",pid_list)]).to_pandas()
        text_dict = {row["paper_id"]: row.to_dict() for _, row in df_text.iterrows()}
    except: text_dict = {}

    q_sorted = sorted(query_sents, key=len, reverse=True)[:100]
    results = {}
    for pid in pid_list:
        paper = text_dict.get(pid)
        if not paper: continue
        other_sents = []
        for sec in ["abstract","introduction","body"]:
            other_sents.extend(split_sentences(paper.get(sec, "")))
        if not other_sents: continue
        fc = 0
        for qs in q_sorted:
            ql = qs.lower()
            for os_ in other_sents:
                if max(len(qs),len(os_)) > 2.5 * min(len(qs),len(os_)): continue
                if lev_ratio(ql, os_.lower()) >= FUZZY_THRESHOLD:
                    fc += 1; break
        if fc > 0:
            results[pid] = {"fuzzy_count": fc, "fuzzy_ratio": round(fc/max(len(q_sorted),1), 4)}
    return round(max((v["fuzzy_ratio"] for v in results.values()), default=0.0), 4), results

def layer3_semantic(query_emb, top_k=20):
    dists, idxs = faiss_index.search(query_emb, top_k)
    results = {}
    for d, i in zip(dists[0], idxs[0]):
        if i < 0 or i >= len(df_faiss_meta): continue
        pid = df_faiss_meta.iloc[i]["paper_id"]
        sim = float(d)
        if pid not in results or sim > results[pid]["cosine"]:
            results[pid] = {"cosine": round(sim, 4)}
    ms = max((v["cosine"] for v in results.values()), default=0.0)
    return round(max(0, (ms - SEMANTIC_THRESHOLD) / (1 - SEMANTIC_THRESHOLD)), 4), results

def layer4_concept(qtitle, qabs, candidate_pids):
    from difflib import SequenceMatcher
    cp = [r'we propose',r'we present',r'we introduce',r'novel',r'our method',r'our approach']
    qc = set(p for p in cp if re.search(p, qabs.lower()))
    qn = set(re.findall(r'(\d+\.?\d*)\s*%', qabs))
    qw = set(re.findall(r'\b[a-z]{4,}\b', qabs.lower()))
    pid_list = list(candidate_pids)
    try:
        df_abs = pq.read_table("bigdata-n9-ptit-final/silver/arxiv_silver_plus", filesystem=gcs,
            columns=["paper_id","abstract"], filters=[("paper_id","in",pid_list)]).to_pandas()
        abs_dict = {r["paper_id"]: str(r["abstract"]) for _, r in df_abs.iterrows()}
    except: abs_dict = {}

    results = {}
    for pid in pid_list:
        info = meta_dict.get(pid, {})
        ot = str(info.get("title","")).lower()
        oa = abs_dict.get(pid, "")
        ts = SequenceMatcher(None, qtitle.lower(), ot).ratio()
        ow = set(re.findall(r'\b[a-z]{4,}\b', oa.lower()))
        ko = len(qw&ow)/max(len(qw|ow),1) if qw and ow else 0
        oc = set(p for p in cp if re.search(p, oa.lower()))
        cs = len(qc&oc)/max(len(qc|oc),1) if qc else 0
        on = set(re.findall(r'(\d+\.?\d*)\s*%', oa))
        ns = len(qn&on)/max(len(qn|on),1) if qn else 0
        sc = 0.3*ts + 0.3*ko + 0.2*cs + 0.2*ns
        if sc > 0.2: results[pid] = {"concept": round(sc, 4)}
    return round(max((v["concept"] for v in results.values()), default=0.0), 4), results

def layer5_self(q_authors, candidate_pids, all_scores):
    if not q_authors: return 0.0, {}
    qa = set(a.lower().strip() for a in q_authors)
    results = {}
    for pid in candidate_pids:
        info = meta_dict.get(pid, {})
        oa = set(a.lower().strip() for a in (info.get("authors") or []))
        common = qa & oa
        if common:
            results[pid] = {"common": list(common)[:3], "sim": round(all_scores.get(pid, 0), 4)}
    return round(max((v["sim"] for v in results.values()), default=0.0), 4), results

def scoring(l1, l2, l3, l4, l5):
    if l1 < 0.05: f = 0.35*l2 + 0.45*l3 + 0.10*l4 + 0.10*l5
    else: f = 0.40*l1 + 0.25*l2 + 0.25*l3 + 0.10*l4
    if l1 > 0.3: f *= 1.2
    if l2 > 0.5: f *= 1.15
    f = min(f, 1.0)
    conf = "HIGH" if l1 > 0.15 or l2 > 0.25 else "MEDIUM" if l3 > 0.5 else "LOW"
    if f > 0.65 and conf in ["HIGH","MEDIUM"]: v,d = "PLAGIARISM","Phat hien dao van nghiem trong"
    elif f > 0.50: v,d = "HIGHLY SUSPICIOUS","Nghi ngo cao"
    elif f > 0.35: v,d = "SUSPICIOUS","Nghi ngo, co doan tuong tu"
    elif f > 0.20: v,d = "SIMILAR","Tuong tu nhe"
    else: v,d = "CLEAN","Khong phat hien dao van"
    return {"score":round(f,4),"verdict":v,"desc":d,"confidence":conf,
            "self_plagiarism":"Co" if l5>0.5 else "Khong",
            "L1":round(l1,4),"L2":round(l2,4),"L3":round(l3,4),"L4":round(l4,4),"L5":round(l5,4)}

# =================================================================
# HAM CHINH
# =================================================================
def check_pdf(file_path, authors=None):
    print("=" * 60)
    print("KIEM TRA DAO VAN")
    print("=" * 60)
    t0 = time.time()

    print("\n[1/7] Extract + clean (9 tang)...")
    full_text = clean_text(extract_text_from_pdf(file_path))
    abstract = extract_abstract(full_text)
    query_sents = split_sentences(full_text)[:200]
    tm = re.match(r'(.{10,200}?)[\n\r]', full_text)
    qtitle = tm.group(1).strip() if tm else full_text[:100]
    print("  Title: {}".format(qtitle[:80]))
    print("  So cau: {}".format(len(query_sents)))

    print("\n[2/7] L1 - MinHash LSH...")
    t1 = time.time()
    qmh = text_to_minhash(full_text)
    l1_score, l1_res = layer1_minhash(qmh)
    print("  {} candidates | score={} | {:.1f}s".format(len(l1_res), l1_score, time.time()-t1))
    for pid in sorted(l1_res, key=lambda x: l1_res[x]["jaccard"], reverse=True)[:5]:
        print("    {} | J={} | {}".format(pid, l1_res[pid]["jaccard"], str(meta_dict.get(pid,{}).get("title",""))[:60]))

    print("\n[3/7] L3 - Semantic (FAISS)...")
    t2 = time.time()
    qemb = embed_text(abstract)
    l3_score, l3_res = layer3_semantic(qemb)
    print("  {} candidates | score={} | {:.1f}s".format(len(l3_res), l3_score, time.time()-t2))
    for pid in sorted(l3_res, key=lambda x: l3_res[x]["cosine"], reverse=True)[:5]:
        print("    {} | cos={} | {}".format(pid, l3_res[pid]["cosine"], str(meta_dict.get(pid,{}).get("title",""))[:60]))

    all_cands = set(l1_res.keys()) | set(l3_res.keys())
    print("\n  Union: {} (L1:{} + L3:{})".format(len(all_cands), len(l1_res), len(l3_res)))

    print("\n[4/7] L2 - Fuzzy match...")
    t3 = time.time()
    l2_score, l2_res = layer2_fuzzy(query_sents, all_cands)
    print("  {} matches | score={} | {:.1f}s".format(len(l2_res), l2_score, time.time()-t3))
    for pid in sorted(l2_res, key=lambda x: l2_res[x]["fuzzy_ratio"], reverse=True)[:3]:
        r = l2_res[pid]
        print("    {} | fuzzy={} ({}/{})".format(pid, r["fuzzy_ratio"], r["fuzzy_count"], len(query_sents)))

    print("\n[5/7] L4 - Concept match...")
    t4 = time.time()
    l4_score, l4_res = layer4_concept(qtitle, abstract, all_cands)
    print("  {} matches | score={} | {:.1f}s".format(len(l4_res), l4_score, time.time()-t4))

    print("\n[6/7] L5 - Self-plagiarism...")
    all_scores = {}
    for pid in all_cands:
        sc = []
        if pid in l1_res: sc.append(l1_res[pid]["jaccard"])
        if pid in l2_res: sc.append(l2_res[pid]["fuzzy_ratio"])
        if pid in l3_res: sc.append(l3_res[pid]["cosine"])
        all_scores[pid] = max(sc) if sc else 0
    l5_score, l5_res = layer5_self(authors or [], all_cands, all_scores)
    print("  {} matches | score={}".format(len(l5_res), l5_score))

    result = scoring(l1_score, l2_score, l3_score, l4_score, l5_score)
    tt = time.time() - t0

    print("\n[7/7] KET QUA")
    print("=" * 60)
    print("  Verdict:     {}".format(result["verdict"]))
    print("  Diem tong:   {:.1f}%".format(result["score"] * 100))
    print("  Do tin cay:  {}".format(result["confidence"]))
    print("  Self-plag:   {}".format(result["self_plagiarism"]))
    print("  L1={:.1f}%  L2={:.1f}%  L3={:.1f}%  L4={:.1f}%  L5={:.1f}%".format(
        result["L1"]*100, result["L2"]*100, result["L3"]*100, result["L4"]*100, result["L5"]*100))
    print("  Thoi gian:   {:.1f}s".format(tt))

    print("\n" + "-" * 60)
    print("DANH SACH BAI TUONG TU")
    print("-" * 60)
    ranked = sorted(all_cands, key=lambda p: all_scores.get(p, 0), reverse=True)
    for i, pid in enumerate(ranked[:15]):
        info = meta_dict.get(pid, {})
        sc = all_scores.get(pid, 0)
        l1v = l1_res.get(pid, {}).get("jaccard", 0)
        l2v = l2_res.get(pid, {}).get("fuzzy_ratio", 0)
        l3v = l3_res.get(pid, {}).get("cosine", 0)
        if sc >= 0.7: lv = "RAT CAO"
        elif sc >= 0.5: lv = "CAO"
        elif sc >= 0.3: lv = "TB"
        else: lv = "THAP"
        print("\n  [{}] {} | {}".format(i+1, lv, str(info.get("title",""))[:70]))
        print("      L1={:.0f}% L2={:.0f}% L3={:.0f}% Max={:.0f}%".format(l1v*100, l2v*100, l3v*100, sc*100))
        print("      {}".format(pid_to_url(pid)))

    return result

print("check_pdf() san sang. Su dung:")
print('  from google.colab import files')
print('  uploaded = files.upload()')
print('  result = check_pdf(list(uploaded.keys())[0])')
