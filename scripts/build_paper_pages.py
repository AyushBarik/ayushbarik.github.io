"""Generate one static HTML page per paper under research/<slug>/index.html.

To add a paper, add an entry to PAPERS, then run from the repo root:
    python3 scripts/build_paper_pages.py .
and add the new page to sitemap.xml.
"""
import html
import json
import os
import sys

SITE = "https://ayushbarik.github.io"
ME = "Ayush Barik"
CSS_VERSION = "34"

PAPERS = [
    {
        "slug": "video-rag",
        "anchor": "paper6",
        "title": "Efficient Video Retrieval Augmented Generation via Token Allocation",
        "status": "Preprint, under review",
        "venue_meta": None,
        "date": "2026/11/24",
        "year": "2026",
        "arxiv": "2611.32938",
        "pdf": "https://arxiv.org/pdf/2611.32938",
        "s2": None,
        "extra_links": [],
        "authors": [("Ayush Barik", "1"), ("Fan Lai", "1&dagger;"), ("Francis Yan", "1&dagger;")],
        "affiliations": "<sup>1</sup>University of Illinois Urbana-Champaign (UIUC), <sup>&dagger;</sup>Equal advising",
        "figure": ("assets/video-token-allocation.png", "figure-video-token-allocation",
                   "Overview of token allocation for video retrieval augmented generation: scoring, allocation, and inference"),
        "summary": (
            "This paper introduces Lembas, a plug-and-play method that makes long-video understanding "
            "with vision-language models (VLMs) more accurate for the same compute. Video "
            "retrieval-augmented generation (RAG) systems choose which frames and subtitles to give the "
            "model, but they do not ask how much each extra token is worth. Lembas treats this as a "
            "budgeting problem: it splits one shared token budget across frames and subtitles, using "
            "the fact that each extra token on the same item helps less, and that tokens spent on "
            "evidence similar to what is already included help even less. It solves this with an "
            "iterative water-filling algorithm that provably converges. In multi-turn conversations, "
            "Lembas reuses the tokens processed in earlier turns and uses the VLM's own attention to "
            "refine what is relevant, at no extra cost. Lembas improves accuracy by up to 7.2 "
            "percentage points over state-of-the-art baselines at comparable compute, and on "
            "multi-turn video understanding it reaches up to 1.5 points higher accuracy with "
            "1.7&ndash;17.3&times; fewer TFLOPs."
        ),
        "keywords": "Lembas, video RAG, retrieval-augmented generation, long video understanding, vision-language models, VLM, token allocation, token budget, multi-turn video QA",
        "bibtex_key": "barik2026efficient",
        "bib_type": "article",
        "bib_venue": ("journal", "arXiv preprint arXiv:2611.32938"),
        "abstract": "Efficient long-video understanding requires identifying relevant evidence while minimizing the tokens processed by vision-language models (VLMs). Existing video retrieval-augmented generation (RAG) methods rely on frame selection and token compression, but overlook how much each additional token is worth. We introduce Lembas, a plug-and-play framework that formulates video RAG as a token allocation problem over frames and subtitles under a shared budget. Our key insight is that the value of a token diminishes within each item and decreases further as similar evidence receives more tokens. Lembas captures both effects in a single objective and solves it with an efficient iterative water-filling algorithm that has a provable convergence guarantee. For multi-turn conversations, Lembas reuses the tokens processed in earlier turns and refines relevance with the VLM's attention at no extra cost. Our evaluations show that Lembas improves accuracy by up to 7.2 percentage points over state-of-the-art baselines at comparable compute. On multi-turn video understanding, Lembas achieves up to 1.5 percentage points higher accuracy with 1.7-17.3x fewer TFLOPs.",
    },
    {
        "slug": "soundweaver",
        "anchor": "paper4",
        "title": "SoundWeaver: Compositional Warm-Starting for Text-to-Audio Diffusion Serving",
        "status": "Preprint, under review",
        "venue_meta": None,
        "date": "2026/03/09",
        "year": "2026",
        "arxiv": "2603.07865",
        "pdf": "assets/papers/soundweaver.pdf",
        "s2": "https://www.semanticscholar.org/paper/a18f85f3e4593a99fcdeede7887d23d88017cabb",
        "extra_links": [],
        "authors": [("Ayush Barik", "1"), ("Sofia Stoica", "1"), ("Nikhil Sarda", "2"),
                    ("Arnav Kethana", "1"), ("Abhinav Khanduja", "1"), ("Muchen Xu", "1"),
                    ("Fan Lai", "1")],
        "affiliations": "<sup>1</sup>University of Illinois Urbana-Champaign (UIUC), <sup>2</sup>Assured Intelligence",
        "figure": ("assets/soundweaver-paper.png", "figure-soundweaver", "SoundWeaver overview figure"),
        "summary": (
            "SoundWeaver makes text-to-audio (T2A) diffusion models generate audio faster, with no "
            "retraining. Instead of starting every request from pure noise, it stitches together "
            "segments of cached audio clips that match the new prompt, then starts diffusion partway "
            "through so the early denoising steps can be skipped. An Acoustic Composition Graph picks "
            "which cached segments to join so the result fits the prompt and sounds continuous, and a "
            "contextual-bandit Skip Gater decides how many steps each request can safely skip. With a "
            "cache of only 1,000 clips, SoundWeaver speeds up generation by 1.48&ndash;3.74&times; "
            "while also improving audio quality."
        ),
        "keywords": "text-to-audio, audio diffusion, diffusion serving, inference acceleration, warm-start, caching",
        "bibtex_key": "barik2026soundweaver",
        "bib_type": "article",
        "bib_venue": ("journal", "arXiv preprint arXiv:2603.07865"),
        "abstract": "Text-to-audio (T2A) diffusion models generate high-quality audio but require tens of neural function evaluations (NFEs), resulting in substantial inference latency. Existing acceleration methods primarily optimize each generation trajectory independently, even when reusable acoustic structure exists in prior examples. We introduce SoundWeaver, the first training-free framework for compositional cross example acoustic reuse. Rather than generating from pure noise, SoundWeaver constructs a prompt-conditioned acoustic prior from segments distributed across cached audios and warm-starts diffusion from an intermediate noise level. We introduce an Acoustic Composition Graph (ACG), which uses neural codec representations and segment-level identification to identify candidate cross-cache transitions and structured path search to jointly optimize prompt relevance and acoustic continuity. We further establish a warm-start error bound showing how prior quality and diffusion SNR jointly govern the admissible skip depth, motivating an adaptive contextual-bandit Skip Gater that selects the warm-start level for each request. Across T2A diffusion backbones, SoundWeaver achieves 1.48-3.74x generation speedup with only a 1K-clip cache while improving generation quality.",
    },
    {
        "slug": "flashdiff",
        "anchor": "paper3",
        "title": "FlashDiff: Efficient Regional Execution and Scheduling for Diffusion Model Serving",
        "status": "Preprint, under review",
        "venue_meta": None,
        "date": "2026/07/13",
        "year": "2026",
        "arxiv": "2607.12121",
        "pdf": "assets/papers/flashdiff.pdf",
        "s2": "https://www.semanticscholar.org/paper/bad55d4f4b3a22d141f4afc9873af33b42c7029c",
        "extra_links": [],
        "authors": [("Yaqi Qiao", "1"), ("Ping He", "2"), ("Songrun Xie", "3"), ("Ayush Barik", "1"),
                    ("Chensong Zhang", "4"), ("Zhengzhong Tu", "5"), ("Fan Lai", "1")],
        "affiliations": "<sup>1</sup>University of Illinois Urbana-Champaign (UIUC), <sup>2</sup>Vanderbilt University, <sup>3</sup>HKUST, <sup>4</sup>Nvidia, <sup>5</sup>Texas A&amp;M University",
        "figure": ("assets/flashdiff.png", "figure-flashdiff", "FlashDiff overview figure"),
        "summary": (
            "FlashDiff is a serving system that makes diffusion models for images, video and audio "
            "faster to serve, including across multiple GPUs. During denoising, different regions of "
            "the latent settle at different rates, and neighboring steps change little. FlashDiff "
            "splits the latent into regions using early attention signals, skips updates to regions "
            "that have stopped changing, and uses an affinity-aware scheduler to spread the remaining "
            "work across GPUs and concurrent requests. On real-world image, video and audio workloads "
            "it cuts end-to-end serving latency by 30&ndash;97% and raises throughput by "
            "1.2&ndash;2.2&times;."
        ),
        "keywords": "diffusion model serving, inference systems, multi-GPU, scheduling, image generation, video generation, audio generation",
        "bibtex_key": "qiao2026flashdiff",
        "bib_type": "article",
        "bib_venue": ("journal", "arXiv preprint arXiv:2607.12121"),
        "abstract": "Diffusion models have become the central backbone for modern image, video, and audio generation, but their efficient service remains a challenge. Unlike autoregressive decoding, diffusion inference repeatedly updates high-dimensional spatial or temporal latents over many denoising steps. This all-region execution pattern makes generation latency high and limits serving throughput. Existing multi-GPU parallelization methods can reduce per-step computation, but often introduce substantial activation exchange overhead, causing communication to offset or even outweigh the benefits of parallel execution. This paper presents FlashDiff, a diffusion serving system that improves inference efficiency through adaptive regional execution and scheduling. FlashDiff is based on the observation that diffusion refinement is not uniform across latent regions or denoising steps: different regions often stabilize at different rates, while neighboring steps exhibit strong temporal correlation. FlashDiff leverages these properties to selectively execute only regions that require further refinement and to reallocate the resulting compute slack across concurrent serving requests. FlashDiff consists of three mechanisms. First, it decomposes the latent representation into coherent execution regions using early-stage attention signals, preserving semantic structure while exposing fine-grained parallelism. Second, it uses a lightweight runtime controller to estimate region activity and bypass low-impact updates when further refinement is unlikely to affect output quality. Third, it applies an affinity-aware online scheduler that co-locates dependent regions, balances residual load across GPUs, and reuses reclaimed compute capacity to improve serving efficiency. Across real-world image, video, and audio workloads, FlashDiff reduces end-to-end serving latency by 30-97% and improves throughput by 1.2-2.2x.",
    },
    {
        "slug": "rewardflow",
        "anchor": "paper2",
        "title": "RewardFlow: Generate Images by Optimizing What You Reward",
        "status": "CVPR 2026",
        "venue_meta": "IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR 2026)",
        "date": "2026/04/09",
        "year": "2026",
        "arxiv": "2604.08536",
        "pdf": "assets/papers/rewardflow.pdf",
        "s2": "https://www.semanticscholar.org/paper/9db9820fbe7f2d8a261b9ac44b7b85f38dc7c4cd",
        "extra_links": [("Project page", "https://plan-lab.github.io/rewardflow")],
        "authors": [("Onkar Kishor Susladkar", "1"), ("Dong-Hwan Jang", "1"), ("Tushar Prakash", "2"),
                    ("Adheesh Sunil Juvekar", "1"), ("Vedant Shah", "1"), ("Ayush Barik", "1"),
                    ("Nabeel Bashir", "1"), ("Muntasir Wahed", "1"), ("Ritish Shrirao", "1"),
                    ("Ismini Lourentzou", "1")],
        "affiliations": "<sup>1</sup>University of Illinois Urbana-Champaign (UIUC), <sup>2</sup>Sony",
        "figure": ("assets/rewardflow.png", "figure-rewardflow", "RewardFlow teaser figure"),
        "summary": (
            "RewardFlow edits and generates images with pretrained diffusion and flow-matching models "
            "at inference time, with no inversion and no retraining. It steers sampling with Langevin "
            "dynamics guided by several differentiable rewards at once: semantic alignment, perceptual "
            "fidelity, localized grounding, object consistency and human preference, plus a new "
            "VQA-based reward that gives fine-grained feedback on whether the image matches the "
            "instruction. A prompt-aware policy reads the instruction, infers what kind of edit is "
            "wanted, and adjusts each reward's weight and the step size during sampling. RewardFlow "
            "reaches state-of-the-art edit fidelity and compositional alignment on several image "
            "editing and compositional generation benchmarks."
        ),
        "keywords": "image editing, text-to-image, diffusion models, flow matching, reward guidance, Langevin dynamics, inference-time steering",
        "bibtex_key": "susladkar2026rewardflow",
        "bib_type": "inproceedings",
        "bib_venue": ("booktitle", "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)"),
        "abstract": "We introduce RewardFlow, an inversion-free framework that steers pretrained diffusion and flow-matching models at inference time through multi-reward Langevin dynamics. RewardFlow unifies complementary differentiable rewards for semantic alignment, perceptual fidelity, localized grounding, object consistency, and human preference, and further introduces a differentiable VQA-based reward that provides fine-grained semantic supervision through language-vision reasoning. To coordinate these heterogeneous objectives, we design a prompt-aware adaptive policy that extracts semantic primitives from the instruction, infers edit intent, and dynamically modulates reward weights and step sizes throughout sampling. Across several image editing and compositional generation benchmarks, RewardFlow delivers state-of-the-art edit fidelity and compositional alignment.",
    },
    {
        "slug": "engdesign",
        "anchor": "paper1",
        "title": "Toward Engineering AGI: Benchmarking the Engineering Design Capabilities of LLMs",
        "status": "NeurIPS 2025 (Datasets &amp; Benchmarks Track)",
        "venue_meta": "Advances in Neural Information Processing Systems (NeurIPS 2025), Datasets and Benchmarks Track",
        "date": "2025/07/01",
        "year": "2025",
        "arxiv": "2509.16204",
        "pdf": "assets/papers/engdesign.pdf",
        "s2": "https://www.semanticscholar.org/paper/db4dfdd1bed4768f051d3c08b9ae2a2c171e5eaf",
        "extra_links": [("Project page", "https://agi4engineering.github.io/Eng-Design/"),
                        ("Dataset", "https://huggingface.co/datasets/opt1zer/EngDesign")],
        "authors": [(n, "1") for n in [
            "Xingang Guo", "Yaxin Li", "Xiangyi Kong", "Yilan Jiang", "Xiayu Zhao", "Zhihua Gong",
            "Yufan Zhang", "Daixuan Li", "Tianle Sang", "Beixiao Zhu", "Gregory Jun", "Yingbing Huang",
            "Yiqi Liu", "Yuqi Xue", "Rahul Dev Kundu", "Qi Jian Lim"]]
            + [("Yizhou Zhao", "2")]
            + [(n, "1") for n in [
            "Luke Alexander Granger", "Mohamed Badr Younis", "Darioush Keivan", "Nippun Sabharwal",
            "Shreyanka Sinha", "Prakhar Agarwal", "Kojo Vandyck", "Hanlin Mai", "Zichen Wang",
            "Aditya Venkatesh", "Ayush Barik", "Jiankun Yang", "Chongying Yue", "Jingjie He",
            "Libin Wang", "Licheng Xu", "Hao Chen", "Jinwen Wang", "Liujun Xu", "Rushabh Shetty",
            "Ziheng Guo", "Dahui Song", "Manvi Jha", "Weijie Liang", "Weiman Yan", "Bryan Zhang",
            "Sahil Bhandary Karnoor", "Jialiang Zhang", "Rutva Pandya", "Xinyi Gong",
            "Mithesh Ballae Ganesh", "Feize Shi", "Ruiling Xu", "Yifan Zhang", "Yanfeng Ouyang"]]
            + [("Lianhui Qin", "3"), ("Elyse Rosenbaum", "1"), ("Corey Snyder", "3"),
               ("Peter Seiler", "4")]
            + [(n, "1") for n in ["Geir Dullerud", "Xiaojia Shelly Zhang", "Zuofu Cheng",
                                  "Pavan Kumar Hanumolu", "Jian Huang"]]
            + [("Mayank Kulkarni", "5"), ("Mahdi Namazifar", "5"), ("Huan Zhang", "1"),
               ("Bin Hu", "1")],
        "affiliations": "<sup>1</sup>University of Illinois Urbana-Champaign (UIUC), <sup>2</sup>University of Pennsylvania, <sup>3</sup>UC San Diego, <sup>4</sup>University of Michigan, <sup>5</sup>Amazon AGI",
        "figure": ("assets/EngDesign.png", "figure-engineering-agi",
                   "Design style evaluation pipeline: LLM responses, program-based simulation, performance check, evaluation results"),
        "summary": (
            "EngDesign is a benchmark that tests whether large language models (LLMs) can do real "
            "engineering design, not just answer textbook questions. Its tasks cover nine engineering "
            "domains, including electrical, mechanical, aerospace, civil and computer engineering, and "
            "each task states its design goals, constraints and performance requirements. Instead of "
            "comparing an answer to a key, EngDesign runs each model's design through simulation to "
            "check whether the design actually works."
        ),
        "keywords": "LLM benchmark, engineering design, large language models, simulation-based evaluation, engineering AGI",
        "bibtex_key": "guo2025toward",
        "bib_type": "inproceedings",
        "bib_venue": ("booktitle", "Advances in Neural Information Processing Systems (NeurIPS), Datasets and Benchmarks Track"),
        "abstract": "Modern engineering, spanning electrical, mechanical, aerospace, civil, and computer disciplines, stands as a cornerstone of human civilization and the foundation of our society. However, engineering design poses a fundamentally different challenge for large language models (LLMs) compared with traditional textbook-style problem solving or factual question answering. Although existing benchmarks have driven progress in areas such as language understanding, code synthesis, and scientific problem solving, real-world engineering design demands the synthesis of domain knowledge, navigation of complex trade-offs, and management of the tedious processes that consume much of practicing engineers' time. Despite these shared challenges across engineering disciplines, no benchmark currently captures the unique demands of engineering design work. In this work, we introduce EngDesign, an Engineering Design benchmark that evaluates LLMs' abilities to perform practical design tasks across nine engineering domains. Unlike existing benchmarks that focus on factual recall or question answering, EngDesign uniquely emphasizes LLMs' ability to synthesize domain knowledge, reason under constraints, and generate functional, objective-oriented engineering designs. Each task in EngDesign represents a real-world engineering design problem, accompanied by a detailed task description specifying design goals, constraints, and performance requirements. EngDesign pioneers a simulation-based evaluation paradigm that moves beyond textbook knowledge to assess genuine engineering design capabilities and shifts evaluation from static answer checking to dynamic, simulation-driven functional verification, marking a crucial step toward realizing the vision of engineering Artificial General Intelligence (AGI).",
    },
]

e = html.escape


def plain(s):
    """Strip the few HTML entities used in display strings, for meta tags and JSON."""
    return html.unescape(s)


def page(p):
    url = f"{SITE}/research/{p['slug']}/"
    arxiv_url = f"https://arxiv.org/abs/{p['arxiv']}"
    hosted_elsewhere = p["pdf"].startswith("http")
    pdf_abs = p["pdf"] if hosted_elsewhere else f"{SITE}/{p['pdf']}"
    pdf_href = p["pdf"] if hosted_elsewhere else f"../../{p['pdf']}"
    summary_plain = plain(p["summary"])
    desc = summary_plain if len(summary_plain) <= 300 else summary_plain[:297].rsplit(" ", 1)[0] + "..."
    title = p["title"]

    meta = [
        f'<meta name="citation_title" content="{e(title)}">',
        *[f'<meta name="citation_author" content="{e(n)}">' for n, _ in p["authors"]],
        f'<meta name="citation_publication_date" content="{p["date"]}">',
        f'<meta name="citation_pdf_url" content="{e(pdf_abs)}">',
        f'<meta name="citation_abstract_html_url" content="{e(url)}">',
        f'<meta name="citation_arxiv_id" content="{p["arxiv"]}">',
    ]
    if p["venue_meta"]:
        meta.append(f'<meta name="citation_conference_title" content="{e(p["venue_meta"])}">')

    same_as = [arxiv_url] + ([p["s2"]] if p["s2"] else []) + [u for _, u in p["extra_links"]]
    ld = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": title,
        "name": title,
        "url": url,
        "author": [{"@type": "Person", "name": n} for n, _ in p["authors"]],
        "datePublished": p["date"].replace("/", "-"),
        "abstract": p["abstract"],
        "keywords": p["keywords"],
        "sameAs": same_as,
        "image": f"{SITE}/{p['figure'][0]}",
    }
    if p["venue_meta"]:
        ld["isPartOf"] = {"@type": "PublicationEvent", "name": p["venue_meta"]}
    ld_json = json.dumps(ld, indent=2, ensure_ascii=False).replace("</", "<\\/")

    authors_html = ", ".join(
        (f'<strong>{e(n)}<sup>{s}</sup></strong>' if n == ME else f"{e(n)}<sup>{s}</sup>")
        for n, s in p["authors"]
    )

    buttons = [
        f'<a class="arxiv-button" href="{arxiv_url}" target="_blank" rel="noopener" aria-label="arXiv"><img src="../../assets/arxiv-logo.svg" alt="arXiv"></a>',
        f'<a class="link-button" href="{e(pdf_href)}" target="_blank" rel="noopener"><span>PDF</span></a>',
        *[f'<a class="link-button" href="{e(u)}" target="_blank" rel="noopener"><span>{e(label)}</span></a>'
          for label, u in p["extra_links"]],
    ]
    if p["s2"]:
        buttons.append(f'<a class="link-button" href="{e(p["s2"])}" target="_blank" rel="noopener"><span>Semantic Scholar</span></a>')

    # BibTeX authors as "First Last and First Last"
    bib_authors = " and ".join(n for n, _ in p["authors"])
    vfield, vval = p["bib_venue"]
    bibtex = (
        f"@{p['bib_type']}{{{p['bibtex_key']},\n"
        f"  title={{{title}}},\n"
        f"  author={{{bib_authors}}},\n"
        f"  {vfield}={{{vval}}},\n"
        f"  year={{{p['year']}}}\n"
        f"}}"
    )

    fig_src, fig_cls, fig_alt = p["figure"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}">
  <meta name="keywords" content="{e(p['keywords'])}">
  <link rel="canonical" href="{url}">

  <!-- Bibliographic metadata read by Google Scholar and reference managers -->
  {chr(10).join('  ' + m if i else m for i, m in enumerate(meta))}

  <!-- Link previews -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{SITE}/{fig_src}">
  <meta name="twitter:card" content="summary_large_image">

  <script type="application/ld+json">
{ld_json}
  </script>

  <link rel="stylesheet" href="../../css/styles.css?v={CSS_VERSION}">
  <link rel="icon" href="../../assets/favicon_io/favicon.ico" type="image/x-icon">
  <link rel="icon" href="../../assets/favicon_io/favicon-16x16.png" type="image/png" sizes="16x16">
  <link rel="icon" href="../../assets/favicon_io/favicon-32x32.png" type="image/png" sizes="32x32">
  <link rel="apple-touch-icon" href="../../assets/favicon_io/apple-touch-icon.png">
</head>
<body>

  <header class="top-nav">
    <div class="nav-container">
      <div class="nav-logo">
        <a href="../../index.html">Ayush Barik</a>
      </div>
      <nav>
        <ul>
          <li><a href="../../Projects.html">Projects</a></li>
          <li><a href="../../blog.html">Blog</a></li>
          <li><a href="../../classesnbooks.html">Classes</a></li>
          <li><a href="../../assets/Ayush_Barik_CV.pdf" target="_blank" rel="noopener">CV</a></li>
        </ul>
      </nav>
    </div>
  </header>

  <main class="full-width-section paper-page">
    <article>
      <h1>{e(title)}</h1>
      <p class="paper-venue">{p['status']}</p>
      <p class="paper-authors">{authors_html}</p>
      <p class="paper-affiliations">{p['affiliations']}</p>
      <div class="paper-actions">
        {(chr(10) + '        ').join(buttons)}
      </div>

      <img class="research-figure {fig_cls}" src="../../{fig_src}" alt="{e(fig_alt)}">

      <h2>In short</h2>
      <p>{p['summary']}</p>

      <h2>Abstract</h2>
      <p>{e(p['abstract'])}</p>

      <h2>Citation</h2>
      <pre class="bibtex">{e(bibtex)}</pre>
    </article>
  </main>

  <footer>
    <a href="../../index.html#{p['anchor']}">&larr; All research by Ayush Barik</a>
  </footer>

</body>
</html>
"""


def main(repo):
    for p in PAPERS:
        out = os.path.join(repo, "research", p["slug"], "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as f:
            f.write(page(p))
        print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
