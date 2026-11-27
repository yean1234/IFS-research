# Object visual properties and egocentric / felt distance in HMD VR: what must be controlled when distance is the measured variable

Scope note: compiled 2026-11-26 from web search plus full-text reads of 4 sources: Creem-Regehr et al. 2023 review, Kelly et al. 2022 Quest study, Iachini et al. 2014, Rzepka et al. 2023. Other items come from abstracts or search snippets and are marked **[abstract/snippet only]**. Items marked **[via review]** are reported as described in Creem-Regehr et al. 2023, not checked at the primary source. Nothing here was invented. When a number was not confirmed, the item is listed under Gaps.

---

## Q1. How do size, shape, luminance, colour, contrast, texture, and eye height/vertical position affect egocentric distance in HMD VR?

### Takeaway
The strongest and best-replicated object-level drivers of judged distance in HMD VR are **size relative to an assumed (familiar) size**, **ground contact / vertical position (angle of declination below the horizon, cast shadows)**, and **eye height**. Effects of **colour hue and luminance** are real in 2D, desktop and AR displays, but they are inconsistent in direction and can reverse depending on background, transparency and object fidelity. They should therefore be held fixed, not assumed to be neutral. Graphics/texture quality has surprisingly little effect on the overall compression.

### Cited Findings
**Size / familiar size**
- Familiar size gives absolute distance only if the object is assumed to have a typical size. Rendering imagery smaller (minification) reduces visual angle, so familiar-size cues signal greater distance, and minification increases distance estimates (Kuhl et al. 2009; Li et al. 2015) **[via review]** — [Creem-Regehr, Stefanucci & Bodenheimer 2023, Phil Trans R Soc B 378:20210456, doi:10.1098/rstb.2021.0456](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- In VR, familiar size strongly biased both perceived size and perceived distance. Rubik's cube vs die at swapped sizes (Exp 1, Oculus Rift CV1). Six sports balls at familiar or unfamiliar size at constant visual angle (Exp 2, Varjo XR-1). Responses were by manual estimation (finger/arm span; spread of two controllers). Exp 2 distance: main effect of familiar size, ηp² ≈ 0.70, p < .001. Exp 1 distance: object identity F(1,52) = 70.9, p < .001, ηp² = 0.56. Exp 2 size: perceived size correlated with familiar size (r = 0.98 monocular, 0.90 binocular); presented size explained little (r = 0.14, p = .65; r = 0.42, p = .18) — [Rzepka et al. 2023, Phil Trans R Soc B 378:20210464, doi:10.1098/rstb.2021.0464](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745877)
- Key contrast: in the real world, binocular viewing reduced reliance on familiar size. In VR it did not, and the familiar-size effect on size was even stronger binocularly than monocularly (t = 2.2, p = .03). The authors conclude that familiar size is "an especially potent cue in VR", possibly because accommodation is absent or because of vergence–accommodation conflict — [Rzepka et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745877)
- Viewing through a smaller (child-sized) virtual body led to overestimated object size **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)

**Eye height / vertical position / angle of declination**
- Distance on a ground plane can be computed as d = h·cot(θ), where h = eye height and θ = angle of declination below the horizon (Sedgwick 1983). In the real world, prisms that increase declination produce underestimation (Ooi et al. 2001) **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- In HMD VR, lowering visual eye height by 50 cm increased walked distance. Raising it did not differ from the matched condition. The effect appeared only when participants strongly felt ownership of a self-avatar (Leyrer et al.) **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Visual eye height was weighted more than actual posture, and eye-height effects were smaller in rooms with realistic textures and scale context (von Castell et al.). Lowering the visual horizon by truncating a textured ground increased perceived distance. Eye-height manipulations "often produce smaller effects than trigonometry predicts" and work best when other scale cues are absent **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Gaze declination is overestimated by about 1.5× (Durgin & Li), which may contribute to compression. Pitching the virtual world 5.7° had no effect on blind walking (Kuhl et al. 2009) **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)

**Ground contact / shadows**
- Floating targets without contact information (e.g., no cast shadow) tend to be perceived as farther away. In the same study, current video see-through AR produced more underestimation than contemporary VR (HoloLens 2, Varjo XR-3) **[abstract/snippet only]** — [Adams, Stefanucci, Creem-Regehr & Bodenheimer, IEEE VR 2022](https://adhocdown.github.io/docs/2022_Adams_IEEEVR_Depth.pdf)
- Object shape and shadow shading interact in perceived surface contact across VR, VST-AR and OST-AR. Non-photorealistic (light) cast shadows can improve perceived surface contact **[abstract/snippet only]** — [Adams et al., "Shape and Shadow Influence Surface Contact in XR Displays", arXiv:2201.01889](https://www.arxiv.org/pdf/2201.01889)
- Shadow location relative to the object can reduce distance mis-estimation in VR **[abstract/snippet only; details unverified]** — [Scientific Reports 2024, "Distance mis-estimations can be reduced with specific shadow locations"](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11053062/)
- Disrupting a uniformly textured ground surface reduces distance accuracy. A restricted vertical FOV hampers use of near-ground cues **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)

**Graphics quality / texture / realism**
- Thompson et al. (2004): about 50% underestimation in triangulated walking in VEs at all graphics quality levels, versus near-accurate performance in the matched real room. Graphics quality had **no** effect. Kunz et al. (2009) revisited this and found that results depend on the response measure (verbal vs blind walking) **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)

**Colour hue and luminance**
- Handheld mobile AR (not HMD): bright colours were perceived as nearer than dark, regardless of hue, and bright red was nearer than any other colour. These effects appeared **only for a high-fidelity simple object**, not for a low-fidelity version or for a more complex 3D object — [Do, LaViola & McMahan, ISMAR 2020, arXiv:2008.05505](https://arxiv.org/pdf/2008.05505)
- VR HMD study with transparent objects, forced-choice pairwise comparison: dark objects were judged closer than bright ones at high transparency, and cool colours nearer than warm at 90% transparency. The authors state these results "reject the classical effects of color and luminance within VR HMDs" **[abstract/snippet only]** — ["Creating Immersive Virtual Landscapes: A User-Centered Approach to Enhance Depth Perception in Head-Mounted Displays" (ITU/METU)](https://research.itu.edu.tr/en/publications/creating-immersive-virtual-landscapes-a-user-centered-approach-to/)
- The classical claim is that warm and bright = nearer. However, the direction can flip with background: warm appears closer on black and cool appears closer on white (Dengler & Nitschke, 2D stimuli). Luminance contrast with the background matters more than absolute brightness **[snippet only, secondary]** — [ISMAR 2020 paper's related-work section](https://www.cs.ucf.edu/~jjl/pubs/ISMAR2020.pdf); [AR/MR measurement survey, arXiv:2210.16463](https://arxiv.org/pdf/2210.16463)
- Method note: HMD luminance needs measuring and linearising before running perception experiments (Murray et al. 2022) **[snippet only]** — [Frontiers / PMC9728491](https://pmc.ncbi.nlm.nih.gov/articles/PMC9728491)

### Inferences
- For an IFS "part" object whose **shape comes from a text-to-3D model**, the main risk is that the generated shape implies a familiar category ("a small dog", "a child", "a stone wall"). The user then reads distance through that category's assumed size. Rzepka et al. show this prior dominates even binocular cues in VR. **Category-implied size is a distance cue** and has to be controlled. Two ways to do that: normalise bounding-box size or visual angle, or record the implied familiar size as a covariate.
- Colour and luminance are mapped from a dictionary and user-adjustable. Their direction of effect on distance is unreliable, which means they cannot be "corrected for" analytically. The safer design is to hold **luminance, contrast against the background, and emissive glow** fixed (or measured) while hue varies. Then log hue and lightness as covariates.
- Vertical position (floating vs grounded) and shadow presence change perceived distance by themselves. A spawning rule ("object floats at eye level" vs "object sits on floor") is therefore a manipulation, not a neutral default.
- Shape complexity: the only direct evidence is the AR finding that colour/luminance effects vanished for a more complex object. I found no HMD study that isolates shape complexity as a cause of distance bias.

### Gaps
- No HMD-VR primary study found that isolates **emissive glow/bloom** effects on egocentric distance.
- No HMD study found that isolates **saturation**.
- No HMD study found on **mesh complexity / abstract vs organic shape** as a distance cue.
- The ITU/METU VR colour-luminance paper's authors, venue, DOI and effect sizes could not be confirmed; only the abstract-level claim was seen.
- Exact effect sizes for Leyrer et al. eye-height studies, Kunz et al. 2009 and Thompson et al. 2004 were not read at the primary source.

---

## Q2. Distance compression in HMDs: current state (incl. Quest-class), and which factors modulate it

### Takeaway
Compression persists in modern consumer HMDs. On average, judged distance is roughly 70–85% of actual, depending on device and response measure. Quest and Quest 2 did **not** clearly beat older HMDs in a direct test. The response measure (verbal vs blind walking) changes the number substantially, so the measure itself is a design choice that must be fixed.

### Cited Findings
- Renner et al. (2013) review: mean estimate about 74% of modelled distance across 78 articles (1993–2012) **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869). Kelly et al. 2022 cite Renner et al. differently, as a 33-study average of 73% — [Kelly et al. 2022](https://www.frontiersin.org/articles/10.3389/frvir.2022.850471/full). *(The study count differs depending on which subset is cited; check Renner et al. 2013, ACM Computing Surveys, before quoting.)*
- Kelly meta-analysis: the newest HMDs average about 82% of actual distance. This is improved but still underestimated, and lighter HMDs are associated with better performance **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869); primary: J. W. Kelly, "Distance Perception in Virtual Reality: A Meta-Analysis of the Effect of Head-Mounted Display Characteristics", IEEE TVCG 29(12):4978–4989, 2023, doi:10.1109/TVCG.2022.3196606 — [record](https://researchr.org/publication/Kelly23-2) (full text not read)
- Quest vs Quest 2 vs real room (N = 93, between-subjects; target 18×18 cm red square on floor at 1–5 m; replica of a real classroom; no virtual shadows, no avatar):
  - Verbal estimates: real 94.5%, Quest 81.7%, Quest 2 74.8%.
  - Blind walking: real 87.7%, Quest 68.5%, Quest 2 68.9%.
  - Both HMDs differed from real; Quest and Quest 2 did not differ from each other. Overall HMD average was about 74%.
  - The authors state there was no clear improvement over the older ~73% figure — [Kelly, Doty, Ambourn & Cherep 2022, Front. Virtual Real. 3:850471, doi:10.3389/frvir.2022.850471](https://www.frontiersin.org/articles/10.3389/frvir.2022.850471/full)
- In the same study, verbal ratios rose with distance in all conditions. Blind-walking ratios rose with distance in the real room but were flat in both Quests — [Kelly et al. 2022](https://www.frontiersin.org/articles/10.3389/frvir.2022.850471/full)
- Spread across consumer HMDs in the literature: HTC Vive 66% (Buck et al. 2018) to 102% (Zhang et al. 2021); Oculus Rift 75% (Peer & Ponto 2017) to 104% (Ahn et al. 2021) **[as cited by Kelly et al. 2022]** — [Kelly et al. 2022](https://www.frontiersin.org/articles/10.3389/frvir.2022.850471/full)
- Modulators named in the review:
  - HMD weight
  - vertical FOV (larger is better; seeing the real floor through the lower FOV improved estimates)
  - minification
  - IPD mismatch (wider rendered IPD leads to underestimated distance and size)
  - eye height
  - ground-surface continuity
  - self-avatar ownership
  - response measure
  - feedback/calibration: walking with visual feedback improved both blind walking and size estimates (Kelly et al. 2013)
  - No single factor explains compression **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Video see-through AR produced more underestimation than contemporary VR displays **[abstract only]** — [Adams et al. IEEE VR 2022](https://adhocdown.github.io/docs/2022_Adams_IEEEVR_Depth.pdf)

### Inferences
- A study that measures **placement distance** (where the user puts the part) will be compressed relative to physical metres. With Quest-class devices, expect roughly 70–80% of true distance and large individual differences. Analyses should therefore use **within-subject comparisons** (part A vs part B, before vs after) rather than absolute metres. As an alternative, a per-participant calibration block (e.g., a standard object at known distances) can rescale placements.
- Because blind-walking ratios were flat across 1–5 m in the Quests while verbal ratios were not, the measure (placement by controller, walking, verbal) has to be fixed across conditions. A drag/place interaction is closest to an action measure.
- Interaction-space distances (<2 m) are the typical range for placing a personal object. Most compression data are for 1–5 m+ floor targets. Near-space placement compression is less documented (see Gaps).

### Gaps
- Kelly 2023 TVCG meta-analysis full text was not read. Moderator coefficients (resolution, FOV, weight, year) are known here only through the review's summary (~82% for newest HMDs).
- No 2024–2026 primary data found specifically for Quest 3 / Quest Pro / Apple Vision Pro egocentric distance. The searches did not surface it; treat as unverified rather than nonexistent.
- No data found on compression for **mid-air (non-floor) placement within reach/near-action space** in modern HMDs.

---

## Q3. Do abstract/unfamiliar objects make distance judgments less reliable than familiar objects?

### Takeaway
The evidence suggests a two-sided risk rather than "abstract = worse". Familiar objects carry a strong size prior that **biases** VR distance judgments, sometimes more than in the real world. Abstract objects remove that prior. Judgments then fall back on angular size, ground contact, binocular cues and context, which in HMDs are themselves weakened or distorted. I found no direct HMD study that compares variability for abstract vs familiar objects.

### Cited Findings
- Familiar-size priors dominated VR size and distance estimates even with binocular cues. Presented (actual) size explained little variance once familiar size was known — [Rzepka et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745877)
- Familiar size yields absolute distance only via an assumed typical size. Realistic VEs with many familiar-size cues showed better sensitivity to eye-height changes **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Adding a familiar virtual human (static or animated) to a hallway model did not significantly improve distance accuracy. Related work found that familiar inanimate objects (chairs) did not improve distance judgments either **[snippet only; primary not read]** — [Frontiers in Robotics and AI 2019, doi:10.3389/frobt.2019.00044](https://www.frontiersin.org/articles/10.3389/frobt.2019.00044)
- In AR, colour/luminance effects on depth appeared for a high-fidelity simple object but not for low-fidelity or complex objects. Object fidelity therefore changes which cues are used — [Do et al. ISMAR 2020](https://arxiv.org/pdf/2008.05505)

### Inferences
- Generated IFS-part meshes will fall on a continuum, from unmistakably familiar (an animal, a child) to abstract (a blob, a knot). That continuum is itself a **distance-relevant variable**:
  - familiar shapes pull judged distance toward the category's typical size
  - abstract shapes leave distance to angular size and placement cues
  - mixing them uncontrolled adds variance and possible systematic bias to distance outcomes
- Options:
  - (a) normalise rendered size or visual angle at spawn and record the user's subsequent scale adjustments separately
  - (b) code each mesh's "familiarity / implied real-world size" with a fixed rubric or rater, not a generative model, and use it as a covariate
  - (c) give every scene the same familiar reference object (a constant scale anchor). Evidence that anchors help is mixed (see the Frontiers 2019 snippet).

### Gaps
- No HMD study found that directly compares the **variance/reliability** of distance judgments for novel/abstract vs familiar objects.
- The cited Frontiers 2019 entourage paper's authors and exact results were not verified at the primary source.

---

## Q4. Interpersonal/psychological distance: does an entity's appearance change the distance people keep or place it at?

### Takeaway
Yes, robustly. In HMD VR, people keep systematically different distances from entities depending on their social category: human vs humanoid robot vs non-social cylinder, gender, gaze, emotional expression (anger → larger) and approach direction. The effects are tens of centimetres. They are comparable to or larger than the perceptual compression effects, so **appearance and valence of the externalised object are first-order confounds for any "felt distance" measure.**

### Cited Findings
- **Iachini, Coello, Frassinetti & Ruggiero 2014**, *PLoS ONE* 9(11):e111511, doi:10.1371/journal.pone.0111511 — [PMC4236010](https://pmc.ncbi.nlm.nih.gov/articles/PMC4236010):
  - Setup: N = 36; HMD; stop-distance task for reachability and for comfort, with passive (stimulus approaches) and active (participant approaches) approach over a 3 m path at 0.5 m/s; all stimuli 175 cm tall.
  - Marginal mean distance (arm length subtracted): **cylinder 64.55 cm**, robot 46.09 cm, male virtual human 45.15 cm, female virtual human 35.80 cm. The cylinder distance was larger than all others (p < .001). Stimulus main effect: F(3,102) = 27.9, ηp² = .45.
  - Passive approach 61.2 cm vs active 33.4 cm, ηp² = .52.
  - Women kept larger distances (58.0 cm) than men (36.6 cm), ηp² = .25.
  - Comfort distance exceeded reachability distance only for the robot. The authors attribute this to ambiguity of a human-like but non-human entity.
  - The authors interpret the pattern as social valence modulating body space. The non-social cylinder produced the largest and undifferentiated distances.
- **Bailenson, Blascovich, Beall & Loomis 2003**, *PSPB* 29(7):819–833, doi:10.1177/0146167203029007002 — [VHIL page](https://vhil.stanford.edu/publications/avatars-and-agents/interpersonal-distance-immersive-virtual-environments):
  - Participants kept more distance approaching a virtual human from the front than from behind.
  - They gave more space to agents that engaged in mutual gaze.
  - When virtual humans invaded personal space, participants moved farthest from agents (computer-controlled) **[abstract only]**
- Bailenson et al. 2001, PRESENCE ("Equilibrium theory revisited"): female participants kept more distance from agents making eye contact; male participants did not **[abstract only]** — [VHIL page](https://vhil.stanford.edu/publications/avatars-and-agents/equilibrium-theory-revisitedmutual-gaze-and-personal-space-virtual)
- Angry vs happy virtual agents:
  - Participants kept larger distances from angry agents and from groups than individuals (Bönsch et al.).
  - Larger distances were observed in a CAVE than in an HMD **[abstract/project page only]** — [RWTH VR group publication page](https://vr.rwth-aachen.de/publication/02158/); [secondary citation in a 2025 study](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12061152/)
- Angry facial expressions in approaching virtual humans increased both interpersonal (comfort) and peripersonal (reach) space (Ruggiero et al.) **[snippet only]** — [Springer, Psychological Research, doi:10.1007/s00426-016-0806-x](https://link.springer.com/10.1007/s00426-016-0806-x)
- Robot-like agents: people preferred greater pre-touch distances to a robot agent than to human-like ones in VR **[abstract only]** — [Kimoto et al. 2023, Front. Psychol., doi:10.3389/fpsyg.2023.1195059](https://www.frontiersin.org/articles/10.3389/fpsyg.2023.1195059/pdf)
- Methodological caution from this literature: explicit "choose a distance" judgments may reflect tacit compliance with instructions. Some designs therefore use a stop task embedded in a secondary perceptual task **[snippet only]** — [Sci Rep 2021, doi:10.1038/s41598-021-83988-2](https://link.springer.com/10.1038/s41598-021-83988-2)
- Approach–avoidance to valenced objects: in a virtual museum, participants approached and looked longer at positively valenced objects. The negativity-avoidance bias did not appear with emotional virtual humans in a second environment **[snippet only]** — [McCall et al., "Wunderkammer"](https://eprints.whiterose.ac.uk/100253/1/McCall_etal_forPURE.docx)

### Inferences
- For IFS parts:
  - whether the generated mesh is **anthropomorphic** (face, eyes, body)
  - whether it appears to **look at** the user
  - its **threat-signalling features** (spikes, dark/red, angry face)
  - its **height/size**
  all shift comfortable distance independently of what the user "feels" about the part. If the dependent variable is placement or comfort distance, these features must be either fixed or measured and modelled. They cannot be left to the text-to-3D model.
- Iachini's comparison of a cylinder, a robot and humans is directly relevant. A non-social abstract form was kept *farther* than humanoid forms. The anthropomorphism level of the generated mesh could therefore move distance by about 20 cm on its own.
- Who moves matters: passive approach gave about twice the distance of active approach. Whether the object is spawned and moves toward the user, or the user drags or walks it into place, must be held constant.
- Facing direction (front vs back approach) and gaze affected distance. Generated objects with an implied "front" or eyes should get a standardised initial orientation.

### Gaps
- No study found that manipulates **colour/luminance of a non-human object** and measures comfort distance in VR.
- Effect sizes for Bönsch et al. and Ruggiero et al. were not read at the primary source.
- No VR proxemics study found that uses **abstract or symbolic (non-agent) objects with emotional meaning assigned by the user**, which is the IFS situation.

---

## Q5. Self-distancing / psychological-distance manipulations in VR where spatial distance to an externalised object or avatar was manipulated or measured

### Takeaway
VR self-counselling and externalisation paradigms exist. Body-swap self-dialogue is the best-known: Osimo et al. 2015; Slater et al. 2019. A DIS 2024 system lets users throw away or spatially confine a drawn representation of negative emotion. However, I found **no study in which the metric spatial distance to an externalised self-aspect was the manipulated or measured dependent variable**. Spatial distance as an index of psychological distance remains mostly theoretical, via construal-level theory. That makes the IFS design novel, and it lacks validated anchors.

### Cited Findings
- Osimo et al. 2015, *Scientific Reports*: participants embodied a scanned look-alike body and a virtual Sigmund Freud, alternating between them to counsel themselves ("Conversations between self and self as Sigmund Freud — A virtual body ownership paradigm for self counselling") — [PMC4564809](https://pmc.ncbi.nlm.nih.gov/articles/PMC4564809)
- Slater et al. 2019, *Scientific Reports*: N = 58. Self-Conversation via body swap (n = 29) vs talking with a scripted Freud (n = 29). Self-Conversation produced greater perceived change and help. The authors relate the method to the self-distancing paradigm (imagining a problem from first- vs third-person perspective). They argue that alternating between bodies matters for the outcome **[abstract level]** — [Slater et al. 2019, doi:10.1038/s41598-019-46877-3](https://www.nature.com/articles/s41598-019-46877-3)
- Mirror distance study: varying the distance between user and a virtual mirror (1, 2.5, 4 m) had little effect on how people perceived their own avatar. The authors conclude that the mirror can be placed anywhere from 1–4 m **[abstract only]** — [Wolf et al. 2022, Front. Virtual Real., doi:10.3389/frvir.2022.1031093](https://www.frontiersin.org/articles/10.3389/frvir.2022.1031093)
- Embodying a dissimilar-looking avatar was hypothesised to raise psychological distance (construal-level theory) and to improve insight problem solving **[abstract only]** — [PMC12796270](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12796270/)
- MoodShaper (DIS 2024): a VR experience in which users draw and manipulate a representation of their negative emotions. Options include throwing it away (paper planes) and spatially confining it. The paper reports reduced negative affect and reduced emotion-regulation difficulties. **Full text could not be parsed; whether distance was measured is unverified** — [Wagener et al., DIS 2024, UCL Discovery](https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf); [TU Wien repository](https://repositum.tuwien.at/bitstream/20.500.12708/203885/1/Wagener-2024-MoodShaper%20A%20Virtual%20Reality%20Experience%20to%20Support%20Managing%20...-vor.pdf)
- "People underestimate distance in VR" is listed among canonical findings of three decades of VR psychology experiments **[page title/snippet]** — [Stanford VHIL](https://vhil.stanford.edu/publications/immersionpresence/five-canonical-findings-30-years-psychological-experimentation)

### Inferences
- With no validated "spatial placement = psychological distance" measure in VR, a placement distance must be validated before it is treated as felt distance, for example against a self-report closeness item such as the Inclusion of Other in the Self (IOS) scale. Raw placement also mixes perceptual compression (Q2), appearance-driven proxemics (Q4) and the felt relationship to the part.
- Wolf et al. found that 1–4 m mirror distance barely changed avatar perception. Spatial distance alone may therefore have weak effects on self-perception, which makes confounds from appearance relatively more influential.

### Gaps
- No study found that measures **where people place an externalised inner state/self-aspect** in VR as an outcome.
- MoodShaper details (N, measures, whether distance was logged) are unverified.
- I did not find VR studies that directly test construal-level effects of manipulated spatial distance to a self-related object.

---

## Q6. Practical recommendations for controlling confounds (size normalisation, fixed luminance, ground contact/shadows, eye-height calibration)

### Takeaway
The literature's practical levers are:
- fix and report the response measure
- calibrate eye height, IPD and FOV, and avoid minification
- provide consistent ground-contact cues (shadows, continuous textured floor)
- control angular/familiar size
- measure display luminance
- standardise approach mode, orientation and gaze of social entities

### Cited Findings
- Choose response measures deliberately, and test whether effects generalise across measures. Accuracy depends on the measure: blind walking is near-veridical in the real world, while verbal reports underestimate in both real and virtual settings **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Device-level factors to control:
  - IPD (a wider rendered IPD gives underestimated distance and size)
  - FOV (larger vertical FOV is better)
  - minification (inflates distance)
  - HMD weight
  - display resolution (under-studied) **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Eye height: match the virtual camera height to the participant's real eye height. A lowered virtual eye height increases walked distance, especially with a self-avatar. Visual eye height can dominate posture **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Ground cues: keep a continuous textured ground plane. Give floating objects a cast shadow or other contact cue, since floating targets without contact cues look farther **[abstract only]** — [Adams et al. IEEE VR 2022](https://adhocdown.github.io/docs/2022_Adams_IEEEVR_Depth.pdf). Light, non-photorealistic shadows may strengthen perceived contact **[abstract only]** — [Adams et al., arXiv:2201.01889](https://www.arxiv.org/pdf/2201.01889)
- Calibration/feedback: walking with visual feedback improved both blind walking and size estimates (Kelly et al. 2013). Walking through a VE also improves perceived size **[via review]** — [Creem-Regehr et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745869)
- Size: in the Rzepka paradigm, stimuli of different identities were equated on **visual angle** at their distances (4.7° in Exp 1; 9.9° in Exp 2). This is a template for size normalisation when identity varies — [Rzepka et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9745877)
- Luminance: measure and linearise HMD luminance before perception experiments **[snippet only]** — [PMC9728491](https://pmc.ncbi.nlm.nih.gov/articles/PMC9728491)
- Proxemics: hold approach mode (active vs passive), stimulus height, facing direction and gaze constant. Each changed distance in Iachini et al. 2014 and Bailenson et al. 2003 — [Iachini et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4236010); [Bailenson et al. 2003](https://vhil.stanford.edu/publications/avatars-and-agents/interpersonal-distance-immersive-virtual-environments)

### Inferences — candidate "must-control" list for the IFS externalisation study
These are derived from the findings above and are not literature prescriptions. Treat them as proposals for the team.

| Property | Why it matters for distance | Suggested handling |
|---|---|---|
| Initial rendered size / visual angle | Angular size and familiar size are distance cues; the familiar-size prior is unusually strong in VR | Spawn at a fixed bounding-box size or visual angle. Size changes only when the participant states one. Log all rescaling. |
| Implied familiar category of generated shape | Biases judged distance (Rzepka) and proxemics (human vs robot vs cylinder) | Code anthropomorphism and implied real size with a fixed rubric. Covariate or stratify. |
| Anthropomorphic face / eyes / gaze direction | Gaze and human-likeness change comfort distance by tens of cm | Fixed initial orientation; no eye contact animation unless stated by the user; code presence of a face |
| Vertical position (floor vs floating) & shadow | Floating without a contact cue looks farther; declination is a distance cue | One fixed rule (e.g., always grounded with a cast shadow, or always floating at fixed height with a drop shadow), applied to all parts |
| Luminance, emissive glow, contrast against background | Direction of effect is inconsistent and can reverse, so it is not correctable post hoc | Fix background; cap or equalise luminance contrast; if glow is user-chosen, log it as a covariate |
| Hue (warm/cool), saturation | Classic warm-near effect is not reliable in HMD; background-dependent | Allow dictionary/user choice but log it; keep the background neutral and constant |
| Texture detail / mesh fidelity | Overall compression is insensitive to graphics quality, but fidelity gates colour/luminance effects in AR | Normalise polycount or texture resolution range across generated meshes |
| Movement mode (object approaches vs user places) | Passive approach gave about 2× the distance of active approach | One interaction mode for all parts |
| Camera eye height, IPD, FOV, HMD model | Device-level compression modulators | Calibrate per participant; one headset model; report it |
| Response measure | Verbal vs action measures differ by ~7–20 percentage points (Kelly et al. 2022) | Fix one primary placement method; optionally add a short calibration block with a neutral reference object |

### Gaps
- I found no published checklist specific to "generated-asset" VR experiments. The table above is a synthesis, not a cited guideline.
- Primary-source verification is still needed for:
  - Kelly 2023 TVCG (moderator table)
  - Renner et al. 2013 (ACM Computing Surveys; exact study count and mean)
  - Leyrer et al. eye-height studies
  - Bönsch et al. and Ruggiero et al. effect sizes
  - Adams et al. shadow-study numbers
  - the ITU/METU colour-luminance VR paper
  - MoodShaper
