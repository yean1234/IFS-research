# Generative models for externalizing inner experience (VR/3D): what prior work says about letting a model decide the shape

Scope note: this file adds to what is already known (Mood Worlds, MoodShaper, SelVReflect, Refugio, MentalImager, Memory Printer, AVATAR therapy, Rocketbox, no IFS-3D study as of 2026-11-23). Those are not repeated here. Evidence levels are marked [RCT], [pilot/feasibility], [qualitative lab study], [design exploration/system paper], [autoethnography]. Search date 2026-11-26. "Verified" means I opened the primary page or full text this session. "Snippet" means I saw it only in a search-result summary.

## 1. Which studies (2019–2026) used 3D models or generated visuals to externalize inner experience, and how was the form produced?

### Takeaway
Few studies actually use text-to-3D to externalize inner experience, and none measure distance. Most generative work is 2D (text-to-image), single-session, n ≤ 12–34, or a system paper with no user study. Systems that do produce a "self" or "inner figure" in 3D for therapy-adjacent use mostly rely on hand-made or template assets (MetaHuman, pre-built avatars) whose appearance is selected or scanned, not generated from words.

### Cited Findings
- **Metamorpheus** (Wan, Feng, Bei, Gao, Lu; CHI '24; arXiv 2403.00632) [qualitative lab study, n = 12 students, mostly non-artists, 1–1.5 h]. Dream → visual metaphor. 2D only: Stable Diffusion 512×512, 30 steps. GPT-3.5-turbo suggests the metaphors. The user writes or edits the prompt from templates, can accept or reject suggestions, can regenerate, and can switch between earlier generations. A metaphor is added to the story only after the user accepts it. (Verified) — [arXiv HTML](https://arxiv.org/html/2403.00632v1)
- **DreamLLM-3D** (arXiv 2503.16439; listed at NeurIPS 2024 creative-AI track) [system paper]. An LLM extracts entities and sentiment from a voiced dream report, and a diffusion text-to-3D model (Point-E) renders them as dynamic 3D point clouds. No participant study was visible in the sources I saw. (Snippet) — [arXiv](https://arxiv.org/html/2503.16439v1)
- **Virtual Dream Reliving** (Liu, Kitson, Picard-Deland, Carr, Liu, LC, Chen; CHI EA 2024) [autoethnography, N = 1 person, 10 dreams]. Whispered dream descriptions become AI-generated 3D objects in VR that the user can manipulate. Reflection was measured with Heaton's Gains from Dream Interpretation (GDI) after each session. I did not find a full text or arXiv version. (Snippet / poster only) — [researchr](https://researchr.org/publication/LiuKPCLLC24); [poster](https://it-u.at/wp-content/uploads/2025/05/06/pinyao_poster.pdf)
- **CyberSelf** (Li, Hu, Li, Zhang, Ma, Zhou, Shen; arXiv 2608.07521, no venue named) [within-subject lab study n = 24 + four-week longitudinal n = 12; ages 21–29]. A self-distancing "self" avatar in VR. Appearance is not text-generated: a MetaHuman (UE5) template is fitted to facial geometry solved from a Live Link Face video sweep, and the voice is cloned zero-shot with CosyVoice. The paper describes no way for users to edit, regenerate or reject the appearance. Users chose the environment and wrote a character prompt. (Verified) — [arXiv HTML](https://arxiv.org/html/2608.07521v1)
- **Worry Gallery / "Pilot study of an anxiety induction method applying generative artificial intelligence and mixed reality"** (TU Dresden; *J. Anxiety Disorders* 2026, DOI 10.1016/j.janxdis.2026.103150) [pilot, n = 34 healthy adults]. Personalized AI-generated worry images shown in multi-user mixed reality. The news page does not name the model, the prompt author, or whether participants could reject an image. The full text did not load. (Partly verified via news page) — [TU Dresden news](https://tu-dresden.de/ing/informatik/smt/im/ixlab/news/worry-gallery-paper-published)
- **Facing your inner critic** (Hidding, Veling, Pijnenborg, van der Stouwe; *J. Behav. Ther. Exp. Psychiatry* 89:102053, 2025, DOI 10.1016/j.jbtep.2025.102053; NCT05887141) [RCT, n = 68 undergraduates with high self-criticism, single session]. The participant responds assertively to an avatar that voices their own self-criticism (schema-therapy chair dialogue), with or without a switch to third-person perspective. The abstract does not say how the avatar's appearance was chosen. One search summary says the user "picks a virtual figure", but I could not confirm this in the primary text, which is paywalled. (Abstract verified via Europe PMC) — [Europe PMC REST record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%22Facing%20your%20inner%20critic%22&resultType=core&format=json); [ClinicalTrials.gov](https://clinicaltrials.gov/study/NCT05887141)
- **Avatar customization and embodiment in VR self-compassion therapy for depressive symptoms** (JMIR-family, three-part mixed methods; PMC12490737). This line of work treats the effects of avatar stylization, customization and mirrored self-representation as "not well understood". (Snippet) — [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12490737/)
- **AI-Enhanced VR Self-Talk for Psychological Counseling** (JMIR formative qualitative study). Users embody avatars for both the self and the counselor to externalize self-conversation. The source of avatar appearance was not confirmed. (Snippet) — [ScienceOpen](https://www.scienceopen.com/document?vid=cc87a546-83df-4578-a993-1d015c1a2d6b)
- **From Prompts to Worlds** (arXiv 2603.13233) [mixed methods on Marble, a commercial text-to-3D world generator]. Studies how people iterate on and make sense of generated 3D worlds. It is not about emotion, but it is the closest evidence on how people iterate with text-to-3D. (Snippet) — [arXiv](https://arxiv.org/pdf/2603.13233)
- **Is it Me? / ProxyMe** (Zhang, Villa, El Ali; CHI EA '26; arXiv 2603.06030) [concept/prototype, no results]. Frames "avatar-mediated self-extension" as delegation level vs. user control vs. self-boundaries. (Snippet) — [arXiv](https://arxiv.org/html/2603.06030v1)
- VR sandplay: the digital work I found covers perception of miniature size (arXiv 2408.08018) and photogrammetric scans of physical trays (J. Visualization 2025). Figures in both are pre-made miniatures, not generated ones. (Snippet) — [arXiv 2408.08018](https://arxiv.org/html/2408.08018v1); [Springer](https://link.springer.com/article/10.1007/s12650-025-01062-9)

### Inferences
- In the externalization literature, "3D model" almost always means a pre-made or template asset: MetaHuman, library avatars, sandplay miniatures. The only text-to-3D cases I found are a system paper (DreamLLM-3D), an N = 1 autoethnography (Virtual Dream Reliving), and the already-known Refugio feasibility study. **No study compares generated, selected and primitive forms for the same inner content.**
- Every generative externalization tool that reports user control (Metamorpheus, and Refugio/MentalImager as already known) includes accept/reject and regenerate. A design with a single generated shape and no candidates or reject option would be less user-controlled than the closest precedents.

### Gaps
- Full texts of Virtual Dream Reliving, DreamLLM-3D (whether any user evaluation exists), and the Worry Gallery paper (model, prompt authorship, rejection option) were not opened.
- I did not verify how the avatar in Hidding et al. 2025 was chosen.
- I found no published study that renders IFS parts in 3D, consistent with the prior finding. I also found none that uses image-to-3D or text-to-3D for pain or inner-voice externalization.

## 2. How often did generative externalization produce a mismatch, and was it harmful or productive?

### Takeaway
Mismatch is reported in qualitative studies as routine. In small lab studies it was usually reframed productively: users shifted from literal fidelity to atmosphere and read unexpected output as a prompt for interpretation. These studies did not measure fidelity or ownership quantitatively. In the one clinical-adjacent quantitative study, how realistic and accurate the image felt **moderated** the emotional effect. A mismatch therefore changes the outcome being measured, not just user satisfaction.

### Cited Findings
- In Metamorpheus, participants found the model "too random" to recreate dream scenes. P11's images kept lacking "crowds, monsters, or a sense of danger." P10 could not obtain a complex scene and blamed either the scene's complexity or her English prompting. Participants then moved from literal recreation to colour or atmosphere: P12 accepted abstract images that captured "the joyful atmosphere." — [arXiv 2403.00632](https://arxiv.org/html/2403.00632v1)
- In Metamorpheus, the system offered P9 an interpretation (contrasting emotions in a monochrome dream) that he did not feel. He treated it as a possible subconscious reading, "like a dream dictionary", and as a reference rather than a fact. The authors frame mismatches as generally productive for reflection and report no harmful effects. — [arXiv 2403.00632](https://arxiv.org/html/2403.00632v1)
- In Metamorpheus, almost all participants disagreed that co-creation reduced their agency. They claimed ownership even of automatically generated results by building personal meaning from them. P6: "Without it I might not know how to express these abstract feelings." P9 and P10 said they would draw by hand if a dream were too hard to generate. The authors caution that the sample had little art expertise. — [arXiv 2403.00632](https://arxiv.org/html/2403.00632v1)
- In CyberSelf, the automatically built self-avatar scored lower than the cloned voice on every 5-point rating: appearance similarity 3.42 (SD 1.04) vs voice 4.08 (SD 0.89), and familiarity 3.50 vs 4.08. The authors note that "some subtle facial idiosyncrasies may not have been fully captured." This happened even with a face-scan pipeline, which is far more constrained than text-to-3D. — [arXiv 2608.07521](https://arxiv.org/html/2608.07521v1)
- In Worry Gallery (n = 34), personalized AI-generated worry images raised subjective anxiety and shifted affect relative to neutral images. The effect was **stronger when participants perceived the depictions as more realistic and accurate**. The news page gives no statistics. — [TU Dresden](https://tu-dresden.de/ing/informatik/smt/im/ixlab/news/worry-gallery-paper-published)

### Inferences
- For the IFS design, mismatch matters in two ways. (a) Qualitatively, users may tolerate or even use a generated shape that differs from what they pictured. (b) Worry Gallery suggests that perceived accuracy scales emotional response, so a mismatched shape could weaken or distort the very responses the study measures (noticing the part as distinct; stop distance). Perceived accuracy should therefore be measured as a covariate rather than assumed.
- The "productive mismatch" reports come from creative or reflective tasks (dreams, metaphors) where reinterpretation was the goal. The IFS study instead treats the object as a stand-in for a specific part. A system-supplied shape there risks becoming the part's form (see §4), which makes the productive framing less transferable.

### Gaps
- I found no study with a validated quantitative fidelity, ownership or authorship scale applied to *externalized inner content*. The scales exist only in creative-art tasks (§3).
- I could not determine how often mismatch occurred per participant or per trial in any generative externalization study. Reports are qualitative.

## 3. Do co-creation loops (generate, select, adjust, confirm) restore ownership and authorship?

### Takeaway
Yes, in creative tasks. Co-creation in which the user has prompt, regenerate and final-selection authority yields ownership close to human-only creation and higher agency. Pure selection from system-generated outputs ("AI-only") sharply lowers ownership and agency. A moderate level of AI involvement beats both low and high. None of these data come from self-representation or therapy contexts.

### Cited Findings
- Wang, Chen and Yang (2026), *Frontiers in Psychology* 17:1986050, DOI 10.3389/fpsyg.2026.1986050 [two between-subjects online experiments, N = 600, Credamo, China]. Study 1 psychological ownership (7-pt, 4 items, α = .874, adapted from Pierce et al.; e.g., "I feel like this artwork belongs to me"): human-only 4.78, co-creation 4.60, **AI-only (select from system-generated images) 3.14**; F(2,297) = 69.83, ηp² = .32. Perceived agency: co-creation 4.59, human-only 4.37, AI-only 2.97. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13690522)
- Same paper, Study 2 (level of AI involvement, which bundles prompt control, regeneration and final-selection authority). Ownership: moderate 4.86, low 4.41, high 3.88. Agency: moderate 4.94, low 4.12, high 3.43 (both p < .001). The authors note that the mediators were measured concurrently, so the serial mediation order is assumed. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13690522)
- A think-aloud study on image generation and creative writing (*Creativity Research Journal*, DOI 10.1080/10400419.2025.2587803) found that control and ownership were intertwined. Ownership rose when outputs matched the user's own intentions or style, and shifted over the course of interaction. (Snippet) — [T&F](https://www.tandfonline.com/doi/full/10.1080/10400419.2025.2587803)
- Xu, Cheng and Kuzminykh (2024), "What Makes It Mine? Exploring Psychological Ownership over Human-AI Co-Creations", Graphics Interface, DOI 10.1145/3670947.3670974. A search summary says higher perceived AI agency was associated with weaker ownership. **I could not open the full text, so treat this as unverified.** — [ResearchGate listing](https://www.researchgate.net/publication/384249704_What_Makes_It_Mine_Exploring_Psychological_Ownership_over_Human-AI_Co-Creations)
- A music co-creation study reports that higher AI automation lowered psychological ownership and state sense of agency, more strongly for experts. (Snippet. I could not confirm which paper in the result list made this claim.) — [arXiv 2611.09918](https://arxiv.org/pdf/2611.09918)
- Felt ownership and warranted authorship can diverge: people may own what they did not make ("authorship legitimation deficit"). (Snippet) — [PMC13751526](https://pmc.ncbi.nlm.nih.gov/articles/PMC13751526)

### Inferences
- The proposed IFS design lets the person set size and position and adjust colour and texture, but the shape comes from a single generation. That lands between the "AI-only" and "co-creation" cells for the most identity-bearing attribute. On the creative-task evidence, adding candidate selection, regeneration and an explicit "this is it / not it" confirmation on shape should raise ownership. Pure selection without any prompt influence did not.
- The "moderate involvement is best" result fits the dictionary-colour plus user-adjust step. Shape is the attribute with the least user authority.

### Gaps
- I found no study that measures ownership or authorship of an AI-generated representation *of one's own inner state or self-part*. Whether creative-task results transfer is unknown.
- I found no IKEA-effect study specific to externalized inner objects.

## 4. Can externally supplied imagery alter or overwrite a person's own mental image or memory?

### Takeaway
Yes. The strongest recent evidence is a pre-registered CHI 2025 study in which AI-edited images and AI-generated videos increased false recollection and false confidence. A companion study found that generative chatbots tripled immediate false memories. I found no study that tests whether a generated *externalization of one's own inner image* overwrites that image, which is the direct risk for this design.

### Cited Findings
- Pataranutaporn, Archiwaranguprok, Chan, Loftus and Maes, "Synthetic Human Memories: AI-Edited Images and Videos Can Implant False Memories and Distort Recollection", CHI 2025 (arXiv 2409.08895) [pre-registered experiment, N = 200, four conditions × 50]. AI-edited visuals increased false recollection. The strongest condition (AI-generated video of an AI-edited image) produced 2.05× the false memories of control and 1.19× the confidence in them. The authors explicitly list "therapeutic memory reframing" as a possible HCI application alongside ethical risks. — [arXiv](https://arxiv.org/html/2409.08895v1); [MIT DSpace](https://dspace.mit.edu/handle/1721.1/162835)
- From the same group: a generative chatbot interviewer induced over 3× more immediate false memories than control and 1.7× more than a survey. — [MIT Media Lab project page](https://www.media.mit.edu/projects/ai-false-memories/overview/)
- Aphantasia did not protect against verbal false-memory generation (*Consciousness and Cognition*, 2025). (Snippet) — [Southampton eprint](https://eprints.soton.ac.uk/506147/1/1-s2.0-S1053810025000819-main_1_.pdf)
- Any AI involvement in writing impaired source memory, i.e. remembering who produced what (arXiv 2509.11851, preprint). (Snippet) — [arXiv](https://arxiv.org/pdf/2509.11851v2)

### Inferences
- In the IFS case, the participant has a vague part-image, the model supplies a concrete shape, and they then interact with it in immersive VR. This fits the general pattern (vivid external visual plus repeated exposure) under which the CHI 2025 study found distortion. Two consequences follow. (a) Later self-reports about the part ("what it looks like") may reflect the generated shape rather than the original image. (b) Source memory for which attributes the person stated may degrade. This supports recording attribute provenance (stated vs. system-filled) at generation time, not reconstructing it after the session.
- The project's principle "do not infer what the user did not say" is directly at stake. A text-to-3D model necessarily fills in every unstated geometric detail.

### Gaps
- I found no study on imagination inflation or verbal overshadowing specifically for *self-generated imagery that is then externalized by AI*. The classic doctored-photo and imagination-inflation literature (pre-2019) was not re-searched here.
- I found no findings specific to therapy-adjacent self-reflection tools, beyond the authors' discussion in the CHI 2025 paper.

## 5. Spatial distance to an externalized inner object or character: has it been measured, and does the appearance source matter?

### Takeaway
I found no study that measured or manipulated user–object distance as an outcome in inner-critic, chairwork, self-distancing or worry-externalization VR. The inner-critic work manipulates *perspective* (first vs. third person), not distance. General VR proxemics shows that distance responds to agent features, and that shape (mesh) drives perceived realism. Appearance source is therefore a plausible confound for a distance outcome, but this has not been tested.

### Cited Findings
- Hidding et al. 2025 RCT (n = 68). Both conditions reduced self-criticism and negative affect and increased self-compassion immediately after the session. Adding a third-person perspective change gave no extra benefit. The authors note that the effect might come from exposure to the inner critic alone. The abstract reports no distance measure. — [Europe PMC record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%22Facing%20your%20inner%20critic%22&resultType=core&format=json)
- UCL embodied self-compassion study (43 self-critical women): the first-person self-to-self condition produced higher self-compassion. The third-person view only reduced self-criticism. — [EurekAlert](https://www.eurekalert.org/news-releases/617287)
- CyberSelf has face-to-face dialogue but does not measure or manipulate distance. — [arXiv 2608.07521](https://arxiv.org/html/2608.07521v1)
- Worry Gallery reports no viewing-distance or placement variable. — [TU Dresden](https://tu-dresden.de/ing/informatik/smt/im/ixlab/news/worry-gallery-paper-published)
- General proxemics: in immersive VR, participants keep more distance when approaching an agent's front than its back, and more from agents with mutual gaze (Bailenson et al. 2003). — [typeset copy](https://typeset.io/pdf/interpersonal-distance-in-immersive-virtual-environments-1qc6vbi4rm.pdf)
- Approach paradigm: Kroczek et al. 2020 (*Frontiers in Psychiatry*) had participants walk toward agents that reacted at set distances (1–3.5 m). Closer distances were rated more arousing and less pleasant. This is a usable stop-distance protocol. — [Frontiers PDF](https://www.frontiersin.org/articles/10.3389/fpsyt.2020.00561/pdf)
- Zell et al., cited in Mousas et al. IEEE VR 2021: a character's perceived realism depends mainly on its shape (mesh), while appeal depends mainly on materials. — [Mousas et al. 2021 PDF](https://people.csail.mit.edu/dkao/pdf/mousas2021ieevr.pdf)

### Inferences
- If shape drives perceived realism and perceived realism or accuracy scales emotional response (Worry Gallery), then a generated shape is not neutral with respect to stop distance. Generation quality, uncanniness, or a threatening silhouette added by the model could shift distance independently of the person's relation to the part. A within-person contrast (generated shape vs. a neutral primitive vs. a user-selected shape) or at least a covariate for perceived accuracy and threat would be needed to attribute distance to the part.
- Placing the object (user sets position) and approaching it (stop distance) are different measures. The inner-critic literature uses neither, so the study would be first on both. That makes a pre-specified protocol (e.g. Kroczek-style) important.

### Gaps
- I found no VR study that varies abstract vs. realistic vs. generated form and measures approach distance. A targeted search for "avatar abstraction proxemics" returned nothing direct.
- I found no pain-externalization or AVATAR-therapy paper (beyond what is already known) reporting distance.

## 6. How do papers report the provenance of visual attributes and the reproducibility of generative components?

### Takeaway
Reporting is thin. The externalization papers I examined name the model and some settings (Metamorpheus: Stable Diffusion, 512×512, 30 steps; DreamLLM-3D: Point-E). None that I saw tags each visual attribute as user-stated vs. system-filled, or reports seeds. HCI-wide LLM reporting guidelines now require the exact model name and version. I found no explicit seed requirement.

### Cited Findings
- Metamorpheus reports model family, resolution and step count (Stable Diffusion, 512×512, 30 inference steps; GPT-3.5-turbo for text). It reports no seed or checkpoint hash. — [arXiv 2403.00632](https://arxiv.org/html/2403.00632v1)
- CyberSelf reports component models (TSTNN, DeepFilterNet2, CosyVoice, MetaHuman) and a mixing parameter (γ = 0.35). The appearance pipeline is deterministic fitting, not sampling. — [arXiv 2608.07521](https://arxiv.org/html/2608.07521v1)
- Navarro, Syriani and Arawjo, reporting guidelines for LLM-integrated systems in HCI (CHI 2026, arXiv 2602.05128). Eight guidelines from 18 authors/reviewers plus 6 experts, including "Always report exact model name and version." Reviewers expect technical evaluation of central LLM components beyond user studies. — [arXiv](https://arxiv.org/abs/2602.05128); [guidelines site](https://ianarawjo.github.io/Guidelines-for-Reporting-LLM-Integrated-Systems-in-HCI)
- "Risk or Chance? LLMs and Reproducibility in HCI" (arXiv 2404.15782) names the unavailability of specific proprietary model versions as the main reproducibility risk. A locally run model pinned by digest avoids this. — [arXiv](https://arxiv.org/pdf/2404.15782)
- MI-CLAIM-GEN extends MI-CLAIM to generative models for clinical AI reproducibility reporting. (Snippet) — [eScholarship](https://escholarship.org/content/qt1c31t56r/qt1c31t56r.pdf)

### Inferences
- Logging, per object, which attributes came from the participant's words, which from the dictionary, which from the generative model's unprompted fill, and which the participant later changed, would go beyond current practice in this literature. It would also directly answer reviewers' likely question about what the model contributed. Seed, model digest, prompt and candidate set should be logged so a given shape can be regenerated exactly.

### Gaps
- I did not open the full Navarro et al. guidelines to check for a seed or sampling-parameter item. I found no reporting standard specific to text-to-3D or image-to-3D models.
- I found no paper in the externalization space that reports attribute-level provenance. This could be a genuine gap in the literature, or a limit of this search (about 25 tool calls).
