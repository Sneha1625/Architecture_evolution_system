"""Combined Architecture Intelligence + Architecture Evolution Streamlit application.

Original app implementations are preserved as compressed source code and executed
one at a time. Keep the existing features/, src/, database/, repository/,
architecture_model/, data/ and other project resources alongside this file.
"""
import ast
import base64
import sys
import zlib
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

st.set_page_config(page_title="Architecture Evolution System — Combined", page_icon="🏗️", layout="wide", initial_sidebar_state="expanded")

INTELLIGENCE_PAGES = ['🏠 Overview', '💻 Source Code', '🌳 AST Structure', '🤖 Structural Analysis', '🏗️ Architecture Model', '🔗 Dependency Analysis', '📊 Architecture Metrics', '🧩 Module Boundaries', '🔀 Logical Coupling', '🔥 Architecture Risk', '💰 Architecture Debt', '🩺 Architecture Health', '🔢 Semantic Embeddings', '📂 Repository Input', '⏳ Architecture Time Machine']
EVOLUTION_PAGES = ['Overview', 'Repositories', 'Snapshots', 'Components', 'Relationships', 'Architecture Graph', 'Snapshot Comparison', 'AI Analysis', 'Architecture Health', 'Database Test', 'Architecture History', 'Runtime Architecture']

st.sidebar.title("🏗️ Architecture Evolution System")
section = st.sidebar.radio("System", ["Architecture Intelligence", "Architecture Evolution"], key="combined_system")
pages = INTELLIGENCE_PAGES if section == "Architecture Intelligence" else EVOLUTION_PAGES
page = st.sidebar.selectbox("Page", pages, key="combined_intelligence_page" if section == "Architecture Intelligence" else "combined_evolution_page")
st.sidebar.divider()

# One GitHub input shared by both systems. No database writes are performed here.
st.session_state.setdefault("combined_repo_url", st.session_state.get("repository_url") or "")
st.sidebar.subheader("GitHub Repository Input")
repo_url = st.sidebar.text_input("Repository URL", key="combined_repo_url", placeholder="https://github.com/owner/repository")


def _valid_github_url(value):
    parsed = urlparse(value.strip())
    return parsed.scheme == "https" and parsed.hostname == "github.com" and len([part for part in parsed.path.split("/") if part]) >= 2


def _apply_shared_repository(url, local_path):
    """Share one multi-language source-file list with both applications."""
    from repository.loader import get_source_files, get_repository_name
    source_files = get_source_files(local_path)
    st.session_state.update({
        "repository_url": url,
        "selected_repo_url": url,
        "evolution_repo_url": url,
        "github_repo_path": str(local_path),
        "repository_local_path": str(local_path),
        "evolution_repo_path": str(local_path),
        "repository_name": get_repository_name(local_path),
        "repository_source": "GitHub",
        "repository_file_paths": source_files,
        "repository_source_file_paths": source_files,
        "uploaded_file_data": [],
        "architecture_snapshots": [],
        "latest_architecture_snapshot": None,
        "github_repository_url": url,
    })
    st.session_state.pop("github_evolution_results", None)
    st.session_state.pop("github_evolution_results_url", None)
    st.session_state.pop("evolution_repository_id", None)
    st.session_state.pop("evolution_selected_commit", None)
    st.session_state.pop("evolution_selected_commit_label", None)
    return len(source_files)


if st.sidebar.button("Load Repository", key="combined_load_repo"):
    if not _valid_github_url(repo_url):
        st.sidebar.error("Enter a valid HTTPS GitHub repository URL.")
    else:
        try:
            from git import Repo
            with st.spinner("Cloning the shared GitHub repository..."):
                local = Path(tempfile.mkdtemp(prefix="architecture_combined_"))
                Repo.clone_from(repo_url.strip(), str(local))
                count = _apply_shared_repository(repo_url.strip(), local)
            st.sidebar.success(f"Repository loaded: {count} source files")
        except Exception as exc:
            st.sidebar.error(f"Repository loading failed: {exc}")

if st.session_state.get("evolution_repo_path"):
    st.sidebar.caption("Active repository: " + str(st.session_state.get("repository_url") or ""))
    try:
        from git import Repo
        repo = Repo(st.session_state["evolution_repo_path"])
        commits = list(repo.iter_commits(max_count=100))
        if commits:
            labels = [f"{c.hexsha[:8]} — {c.summary[:65]}" for c in commits]
            selected_commit = st.sidebar.selectbox("Select Git Commit", labels, key="combined_commit_label")
            st.session_state["evolution_selected_commit"] = commits[labels.index(selected_commit)].hexsha
    except Exception as exc:
        st.sidebar.warning(f"Git history unavailable: {exc}")


# Real GitHub architecture snapshots, using the repository already loaded above.
def _render_real_github_evolution():
    if section != "Architecture Evolution":
        return

    with st.sidebar.expander("GitHub Commit Evolution", expanded=(page == "Architecture History")):
        repository_path = st.session_state.get("evolution_repo_path")
        repository_url = st.session_state.get("evolution_repo_url")

        if not repository_path or not repository_url:
            st.info("Load a GitHub repository first.")
            return

        commit_limit = st.number_input(
            "Recent commits to analyze", min_value=2, max_value=20,
            value=5, step=1, key="combined_evolution_commit_limit",
        )
        if st.button("Generate Architecture Snapshots", key="combined_generate_snapshots"):
            try:
                from architecture_model.github_evolution_pipeline import analyze_recent_commits

                with st.spinner("Parsing historical Git commits and saving snapshots..."):
                    results = analyze_recent_commits(
                        repository_path=str(repository_path),
                        repository_url=str(repository_url),
                        limit=int(commit_limit),
                    )
                    # The snapshot page must represent this request, not an older
                    # accumulated history. Keep only the requested batch in session state.
                    results = list(results or [])[-int(commit_limit):]
                if not results:
                    st.warning("No commits were found.")
                    return

                repository_id = results[-1]["repository_id"]
                st.session_state["evolution_repository_id"] = repository_id
                st.session_state["architecture_history_repository"] = repository_id
                st.session_state["github_evolution_results"] = results
                st.session_state["github_evolution_results_url"] = repository_url
                st.session_state["github_evolution_requested_limit"] = int(commit_limit)
                created_count = sum(bool(item["created"]) for item in results)
                st.success(f"Requested {int(commit_limit)} commits; {len(results)} analyzed in this batch; {created_count} new snapshots.")
                extraction_stats = [item.get("extraction", {}) for item in results if item.get("extraction")]
                skipped_large = sum(item.get("skipped_large_files", 0) for item in extraction_stats)
                skipped_limits = sum(item.get("skipped_total_limit_files", 0) for item in extraction_stats)
                if skipped_large or skipped_limits:
                    st.warning(
                        f"Analysis continued with supported source files. "
                        f"{skipped_large} oversized source files and {skipped_limits} files beyond the repository processing limits were skipped."
                    )
            except Exception as exc:
                st.error(f"Snapshot generation failed: {exc}")

        if st.session_state.get("github_evolution_results_url") == repository_url:
            results = st.session_state.get("github_evolution_results", [])
            if results:
                st.caption(f"{len(results)} commit snapshots available")


_render_real_github_evolution()


# The Architecture Graph page is snapshot-scoped: it must render the selected
# saved snapshot, not a graph rebuilt from the repository's current HEAD.
if section == "Architecture Evolution" and page == "Architecture Graph":
    st.title("Architecture Graph")
    active_url = (
        st.session_state.get("repository_url")
        or st.session_state.get("evolution_repo_url")
        or st.session_state.get("github_repository_url")
    )
    repository_id = st.session_state.get("evolution_repository_id")

    try:
        from features.architecture_history import get_repositories, get_snapshot_list
        from architecture_model.snapshot_loader import load_snapshot, get_snapshot_info
        from architecture_model.github_evolution_pipeline import normalize_repository_url

        if not repository_id and active_url:
            normalized_active_url = normalize_repository_url(active_url)
            matching_repositories = [
                item for item in get_repositories()
                if item.get("url") and normalize_repository_url(item["url"]) == normalized_active_url
            ]
            if matching_repositories:
                repository_id = matching_repositories[0]["id"]

        if not active_url or not repository_id:
            st.info("Load a repository in the combined sidebar and generate its architecture snapshots first.")
            st.stop()

        snapshots = get_snapshot_list(repository_id)
        if not snapshots:
            st.info("No snapshots exist for the active combined repository yet. Use 'Generate Architecture Snapshots' in the sidebar.")
            st.stop()

        snapshot_options = {
            f'Version {item["version"]} | {item["commit_hash"]} | ID {item["id"]}': item["id"]
            for item in snapshots
        }
        selected_label = st.selectbox(
            "Select snapshot for graph",
            list(snapshot_options.keys()),
            index=len(snapshot_options) - 1,
            key="combined_architecture_graph_snapshot",
        )
        selected_id = snapshot_options[selected_label]
        selected_snapshot = load_snapshot(selected_id)
        selected_info = get_snapshot_info(selected_id)

        if selected_snapshot is None:
            st.error("The selected architecture snapshot could not be loaded.")
            st.stop()

        st.caption(
            f'Graph generated from snapshot {selected_info.get("version", selected_snapshot.version)} '
            f'| commit {selected_snapshot.commit_hash} | snapshot ID {selected_id}'
        )
        components = list(selected_snapshot.components or [])
        relationships = list(selected_snapshot.relationships or [])

        if not components:
            st.info("This snapshot contains no architecture components.")
        else:
            def _graph_quote(value):
                return str(value).replace("\\\\", "\\\\\\\\").replace('"', '\\\\"').replace("\\n", " ")

            dot = [
                "digraph SelectedSnapshot {",
                "  rankdir=LR;",
                '  graph [bgcolor="transparent"];',
                '  node [shape=box, style="rounded,filled", fillcolor="#E8F0FE", color="#5B78A6"];',
            ]
            node_lookup = {}
            for component in components:
                node_id = str(component.id or component.name)
                node_lookup[node_id] = node_id
                node_lookup[str(component.name)] = node_id
                label = f"{component.name}\\n{component.layer}" if component.layer else component.name
                dot.append(f'  "{_graph_quote(node_id)}" [label="{_graph_quote(label)}"];')
            for relationship in relationships:
                source = node_lookup.get(str(relationship.source), str(relationship.source))
                target = node_lookup.get(str(relationship.target), str(relationship.target))
                dot.append(
                    f'  "{_graph_quote(source)}" -> "{_graph_quote(target)}" '
                    f'[label="{_graph_quote(relationship.type)}"];'
                )
            dot.append("}")
            st.graphviz_chart("\n".join(dot), use_container_width=True)

        st.subheader("Snapshot Contents")
        left, right = st.columns(2)
        left.metric("Components", len(components))
        right.metric("Relationships", len(relationships))
        st.dataframe(
            [{"Component": item.name, "Layer": item.layer, "Files": len(item.files)} for item in components],
            use_container_width=True,
            hide_index=True,
        )
    except Exception as graph_error:
        st.error(f"Unable to render the selected snapshot graph: {graph_error}")
    st.stop()


# The original applications are embedded unmodified. AST adjustments below
# remove only their second page configuration and redundant navigation widgets.
APP_SOURCES = ('c-rl~ZEqt<njrRFzapKD-X=8^OQouw>64ocuq2jBUcH^DszIM1u#;p`%&8=kmzk^*TPI*{y|*9iwP!s$zQG;V==0iVV-3SNU~$IY8n_?Rf8hEjIG%{e%!tT%OEOhcJ!k>lC6V#^#1qe3JTI>6Zgr1$y8Zrf|EhQB^v_>j{jz)6bGnxYua2*J2UoArAIE1`y_1vUqu$v;&*^`STAprg9YnG3jJ$<648kA{{A7RYY1`>X%XsAPjH0pcBx$@HrOVh09dGW1t0YLa_S#Oje^vbb4E-ICra|gMOW%q8QS{D_S6k29&V?VNCaFJ99gl63%)Lc2jnZW6^R{z5PyN^%rNKL&Z}l!nmR=Zq>!m?7-}-smIrJC)eC*Fht77_Jw4Kvsm<BtOAQbxNZN3neIP=pu7$sZ(r0twUx4{T)Zxk&TVKBcfIz8P*BS+&U8g&>g=VLEkIb$D&fYm&GDsDSS-ZGu{gs;c`FlD|*K<oQ6Z=MDt$Da-T@fgjWI1@Y(nE-+BC`ex|hX|sJC<)RiX12Y>jeZr(eCO0dpUnOJEeHKvl2Z@>k~&j#98rw7j7CS>p3Q<ZLF10$_k|bxxV!wc96V%-CTnkPy<EbVWHxp&JKlRVigVdL!e8~?1#n{i&TR~v^T)!H5<n0H2;BIWQ!m{KCc^Z=Y#9=uxCq&|K5;r5{Gjf~rx)j!SN%-~+6rciC{CRy$$m>#`LC%zTL4C8e|t%~HHo8{v+&Ys7z`cy`33qj9|>JI-<zSkh?=86vXAF}`aX)^-odByyX@0N7^UH=eH(j==^z^Z3PCG@7PrwBndugdL)%^=3?d(nBXk?zWuJ$UHy)6WXs09|wa3LZqwN~_bcV|yM9uSW2YBul{%#z5?-gH>ZV0=E2s>r{n{;l3`QFe={5FH|+yWBsoj)kPY!x47D9U^U=p4-v>1nZj2_hxaU_m~<_0zm_QhbzmW<Fy(CwSExW8y{k>XmbFe)jVC==Ejy>iGO@W2Ai1?e_+U$CpkAA!Zw}tvwFnxi|9(46_ftVFLd)1_MCT!Jr8nLRT;EKaUXl%mJry2XfJ~zuLh(@#D0y+sZqj?k{^?;5L0>{$EAGoJ^jzB|vp2z6Uovaa(k9ZUEZ_u$|B_o1aSW?9K7z`Ppgj>}uoVU~X6gEv|ogFhIlG00-Sfm;TyDy>l349sN5*IFkk)u}Q$gPM3XC2S_e^7w7%stMkjRYong{$`_Zp4NFJdg}d;h5M9CnB4pF$uypbLyA;HR0b<<HbzEvdE^YSN0PaBX#bT9Cqd7)?a+zzm&6nr@4U)I&g%A*A#Fi5gH25>Te6lCRImXPNn652nGY^2#WX8f0#JA#T^wR+z6(E@)nM&xG@njiO5IKQB*=y!1?65?768D2YmF#BoL*~Tl)APgL$;RiL#;g4;yllKHR`?mrkQg4eGnty-Bsq5c&4BGhVAmu=vg;k-^$xmky2mHo7biVLhOXkJzqRGxjr>LG9OKb@aU8|_R=r<(VdB>T)$<Ere%%uuycuP$8^RgiX=hUZV1`7KxC~wRcn}g5VURWEz<Y51`r_pH?5GM*rF}9`s+T&OE$2bH8W1HUk}Nm7#WPS_ycjhW)_QvS`t11X>uQUYbuz6Mw4uQw_Q!#Ir66A|QzVc<yJUnE(S%#-<#GQ{tE{rr-n2lpBH$gGCDN}3qp3H)^#`N_w@5_iy9ZZQmMQ6BS|~c}DOMiKF!aI^C`SGO+RQPILQ8Iq=qkM$9QIyRTBf{HZI}I`d(^90>P^yi0!-bz1;Kwl32rkki9Se!H1s<zr!j-kAq<0CP)(iwDna@hm9}t~01eV{fB5b<zyB})@EiI?=&hn<+Hv0_g_eF4pbHrwuqWuFp%)L3CYz#}{JVt*s;*lT&pCMAzdAp44*Hu@!v59QC%pmIJ8WdobQSvTQIaU7&wRKh#hn6=;paUP-JA&V?*eV%r|8z=K6hi6{{S6N1g4RWyG$oLUohV`LD!uyQ(^5OZ6k^2?KpZbOo;E5`z7AbSND@PNK1|8!<SFUC&H}ovz#a1#2<KJ7`-1%(^=SoOT)LLcZ}Yn9{vX@h|HoEUXs*-0sUUTkM0QqT=%NCF%lg1UUpxfTn*@`13W6ihkLScH<zffY6xn%yYF1zwCLB2JU#$qKwq9AIX(ND5xEm=OH_XkBDwloJUdK~aMLp_!U%|-ehtew6utzSnWUV^l-mG=rqVY2a){*;lOFUr(2RfQoFkF!UEse*c(wI_&VPa!%v*oea>o9|L$c`Lofj^B&~Bwi(MD6wl16r=(6vLIbA1>{U6LR?Bjkp`Hu0-#)a?eHD>rK$=y=$@>H?{7o;dxp?nVFA`IU3gyTm5wvxChM6fKw-Y^3lXq|qR=6;Z<wXa14ud?l>xkaHHkL)b#Upc*xp9N}MT%0@C4XYK6MnbFClk<<UDC+Ledl}UWmV4mzVvU)yEFmC0GMt|fp;a@&+cGmo%-NA~FpvO$O>9|{^^&_+r%y9+91*mtVr+^QOfWLGgMGH6t{!BQTW@Gs5wGpw##)JG2(D|WDIwNN0I)Fti>w~G6OcAJ%I_{-uT!4tjSbY3U4~8GP%lX?m;%6=gf_H$8(cE%m+L{@)!2P;l`i$b7^yQ!yh%)yjL%!^zhWw6o_#4M+9~q=O%<n}53a}3Sw_Zp+r;sXa%yl6g9nK!#Xa@!{fUhx|1;&-P1MX9FV)zc+Z`q{WvII#Fv;LMKy~T~Zd6N<Kwzf*64bs)3@|=8cVfNxm2y^nU3H(e9PIj2z`H?X><Y{1eFCG5R(n>Z)yU%l`z&vBr#21(mEs>AwqsKqCDWD+Nm6d)l7g6Cv`RONL3zbqW(INF>G{G9vkdC&~Afb<LC`fQCQPt7zR=*VT_!3960<9$)5WlqY@+ctW%hN;2VtGi$TYGT?HUk}55=9OjO(JcZ8f?%`MVi=6McT@zVgaTle;OPtjZqmL$yUK%fZ4i;o8nt*`Sh&_CnGH~lb73&m2{W|wY2C)2yW>UDL%zmigy$eMr%v5p`3!%`tJ6scLFL_ExHw_LW8E?5VRelyI?yZ9KFZ-pdgZ*83>#U{EFt_S2XH4f&`mo9HUzst{m^37lht0L@E)d;ZUFsqbO`BwbwQ}%!Y`*GUEV)ui0;CjTXa6>>R>aaEJgf>=Qt?#Xc$G7xYX`FJVfx4KcQiwKr6<%&4{#aNEd_NrwjSr~ceYr|j`kBw%m@iP5;@GJ)Z+ixKfST9q(>E|Cy1HE?qi2$(<eUaV4$mq?A%WeX&9L34lyj7TNvSaMn`oF$gy=nC4y%uT9zcp*?|PknFP4id1m1n5$2*;@+vedI_-h}1js(mN>JICAta87dB<IZ|6v#~UV5xJ+3q0Pcl7kg&NzQ0jNGxo`{dyrL+zJ}PL;Y>ht<X0w?w8BL5wD4T4HU6$y16s1Z5Km+H(D$6V+pJywhkN<ob#QuOI5S&3S!-WzRWpDp`FP;bUTj7%a@ZDeknRC8Cw`qGD|9)8<(D8h+Ot-f&Lcy4b^16KQl22gE`De!$+~0^+uyh&yKSqmjrMeBGDQUE5G=+`x1cD)Pa=36{(GeFL=={~cajp>2$ezHmNfVw6;g<z`%{VF}g6o6;vFu4Xisq>ozycg_fc&P7mi<jWj1gEHbN1I4C+FS6-l6mI_@q}Wb05V%c@&&21iUSHCc4VkH{?V9EWxs(<ufv-sa4;=mJMnfKaZ9?q_YKDN9ID=K0{P*eC5M4r5CSWqL0dyV(f>0>US{tln9Z_$t1Yzxb4NtRT2$4bNhXamRz0z_Hpgv{oa^{7==;dH-s+==(oKExU`h#fWAQEZRr}kf%)Y(FzL-APhbbpG92S;O3(yD8N-z@2UpSuPVt+2*gr;v&tQe0wVcnWW%9G;!#DfRz5n29<mY1Zl+qCYB?W;M<U9+kluL$6#0(~-IT$c<_asClp)5JDJxg33;h<_X$>rQC{JDxtnB7jQ_lO_Ekx)L)jIX^^WCAos;W<`D5KbPFAa`zc$lcAVkHPL#c@sz@^HL1MkVYTkI^hMQYXZBsxDO2pdbGA=AQB%=*iY;6E;#9R&k#Ryu6p3O*hRV~@T8iUQRsW~<$^`{V#9*u+V>`Y2s*@kj3^Q9=|mHTM&*hpIri+KjT3MaXSPhhYaW6XhCXEt<2E;!(ib072f>G*s1>k-F%m>Zc%}|+-pH90B1iB$YS3slkwlAx?{_&1kkGUHE!OUX$AaZBT?_4jz3ppj$t@rrygK+$5R<&2o}!5NJOe}CqqOzx=M(1)9|$=OB%=nm!Q2Z)?Ihtkfz=5?2M<h4zaq^RuOx_d!F=h9lb_E+Ec1b<PE64xz<)8=m7lJ-2y(%}>pUqmvNUS&IMK9UPA1I+A<RmYWegdhLQB*qbl&^$3>8dPLf2{ZUdBb}XG!Ub@V)Uamh&)}zipT);aYM9+*`B?L9&oj#G3tak1o3xuj&+{IsXIfecU)|fj36SEq~?a`XQws!OYLajidH_IUD-%Aes#3(HI|Dr{nDI%TyxwEaD$haSwzNIFbxLMD)yU3dV!%p=j-$lkWX1?C^JXe%N!)FAsZ{n-050j3;A17pD*~2nh1Wt&1h-aJN%(OXqlpw2$w_Vc^GYZkPlC*k>3%{=8t7a6+Ls8;(6^zK>u(_HSd~Z_F9XdJN<!@fo+SX07l$>3)6w`l=S#A#D-K7M>G=fjf4Rg*O7dl{gV45e15e@dOCf=q&<X8X?Xw&ESUUCW6}huAMAmaCj!pj0OCT7%{{5$DQYU3@|&-+n*PI1`w`^4d<P`-Cd^N$P4|>(_P`Ud{bz0o^N$PGfDl$03511h;H4ZUmgbV5ur`-at=38_?~|1=C?T?L+O;I^vTM)f@9Whp^Y%}Rv(k;eN%Yq)&l>7^RuhV^OJr}pfCJ0-A_LG#QEX7|MCCk17+W^LBB4=B8Y+@I$-RL1ICc+a?K%LmwnN?7EMe4)4yb0^Mo(|ufK8n=xla|s~z}PZ1DZR{(qep5Ub*J=K*mPVw&6(zfO^C^DS7HM3+$@N*PAYij~%NQ_kP?F5evYep$;&A(SLQ?}%_?M8bDL5)8pCO^Gu8w>B=+yKr87jsLA>M}ElfNjz?5U!$ijXS9d@dxrjdP7rSth0EDIX*_QV-p!+@`(>H6JzS<~BymD^zyHnugA|s;mpy8;2ofvWEEDYE4z^1qOuP@q=~U*KToy$Qgh<jn_7Poal=iz<ZNI<&wR3@ZZ4fOJ!<HB7W{<P$nRi!SG5qYdq#tVr+i{+j`!p*+^;spTp80pFgD8>#qI1+t(gZ($yGRg#@W2lT?O-m4cIeL=m~=ENgZ*clg8g|($sx%hBrxaLl!QYNMd)6=+6U)}b6;%sL2Zhb5>}p@?W^Z0m=gDPv4|ri1Sd&j%M!Rx@C9K`$9dXR_=bSU!Y#T4R`9Qt0QDdYMsJ<%?F^x}w~^qA+IvWU!jYjM=)$Wrs}8lLmbHypPWScI`Dyp+_`vC&9iNiGq<T0HXAds83(r}e$v6uS#)Xe9xcJOM1dBluf;~fqteK4B^r4dkRig!w;jg84&V2*nru{H_@5(QwtNZQ@T&Y9Vw=caURegu2RW!IMe}q+_j(R?p7$y=xu&;aYH3^a6?Q;S+_MP4K7lLe<fAP8S1zi|?wI_aucM0D--D_<rfB;|bG94cz%(xOaMnY^KUoM#tYs()vsKRJ}SUE+j3z1OA60fZSv>(3v-Je^@Y+eS_k3o8~&=76d<a*A*O!teE?m_R>`N?7L(s_A)>6{$D$qaQH&XM;gIdB%CH}a=Z2nJqEBmLPTT`^8L83R<e+~P4p4MG8du$w$}i-Ci|wrU6)Zd5qPGPV?~w=C#1g(X;u4Y~NhF1Ji+%VSqNBT4rcua8d-o!;S5ukW0noqX-Q=w1D?*E@6G9QThigJXZwd6h6pus3odK9)#9Cy^+X<ND)U@-izOmii92sEcY-+6b_RZwL5u)W$<M<b4?T@Hx9jY2(6M*VOtk4jzsiM-0|}wg8~P9eEa)ez#(t%*_zzj#P5JDBR@;#JrAE``sc+lr7QxbY4Sa2`kXQEoDD<yDew63(x&ga!nR?BX5Yr(bZGhkSyv(J|qEm8%gTYxAxrX22;bR;7l%`v#FV2Wu9OKd#gGD9vp)Hu-|;t?vK1QmC4Q+C>^p{xs<vh->&4}f{m%;hKR!_3Mm)9>p*e|^&W|6@U*=r-=2KjDWrk{MXTe^5op|&4I$h3e&dItN4eiXj8*p=f49<nmx4yA{u;wdLmr?JOBAS9E5{auj`RXSGsX2GyUAQt?waaGtE|yVaZy5V=!aNziPb1XAKA!~%5DNBF&7W2z}W2PLh7blmT_V%w=}gan{CLtp`Nc<g>>Xcu5<<BU{`r)j4sBpC+?TSukP^-4_`hRe)Z)r{>s&~J|It>poi}}x`y|~6DGj*!L{80fr~ZOBRHy}dIULjR1aQv{5bhpDmOe5KbpI=lOLD54fgbaAY3<%7S70rEU}s)Cx{ywXlfFC3-6PaDQdA|{HKxjYBo>cW3$e^=jxkb!9Q3Y^11qowQPa$7>onw|LN7vH73C=!S$EH?K1Y|Fakebh3ShI7SyLuTrGK<8yg^^#kQA=G5DH@Px2gw;}k~s%C!)j+t(9#n$9T84eXDdel$sOwqDk@tziM~oy^L`xA5kpX%s^$6z!dTP}usX(fiQ9MO0Sh%Z)FaAKXsU&M$U%HJ6c4B<zZvXzt@}FgM(#Vdwd-<}zx(jkVvVoiBD<Rp`;3cNZik@_|5j8wXkd!q2yU9AQdgXb0n^!RRe!Yl*2fHhXAp7X0iyeX18Tbl=}p0@&&&fZc3D<V&WtHpx2;Y4KtOOc70!PibfU)LT~XS;N(Xor)tf{3)Kpa^;$}<~>or6x+OC;sdILwOHcNiJ335r!n?f%pgK?fJ1xIHfEkFnVcW)2AHI^V4DxYW(u5{J_&t)As>%@;<?6u7<qIBS1ZX=Uj?JA&3i6mq1*Ve^YF6!OYBs4e85=a>v9|VuR3yvDT(ut!Z0g0$kzEVflbl1y+O!qky0C^!P;AXno>ozWTr!%J-1|MR5iBtUAI_}%$8|1cv>&OXxKCxG!2GKjRCVM8Axrg)EFw80_K=hbh$xNZirMHAT^4k+~6pXcC~@A&Wp)E1Z{dTWky7q@latjR2mCyjf8sRpw=j;HwJ2rfR@HTt<g_!?9&_hRK~rg?mC%`cxB_AYzV!v&dx|@G|rifa!mmR%{N?Te3Kj9jK(&dk<HS$W-zMBjA=4zp*5cAjb>V7nbJsRFpjB>V#4a1k3-x9qt~X?O>68@7`b%DEtOI0Mg|On@k(X1(iy8ZFjA?FQ%0kdV2simp;X2vqtQugY?2$9<i;hrQK@W95-?h4JTlopOtufR%|lqs>SI|9pWs7n-6&Z#?5r7ruN+#IE6MG+p)z;cySh9+s3%6p<eoZuT5^%*U84_Vc}2mVz)49>F8F1%S03~YX^tp?JXK_}obf00bZcF&8qS*rR8fAZTWV(-O=Dq)&&oTzic&9>!%Gq_$_6QF14_+FcC5ln)p@bDY6vOZYwt=!3ZL%s0feGnUDB!T_34u8s#jaJDyyKbmQ_`)nyOb(HR`ECH5Ii<xk{=~M_EAYgw(PMT2?>hs%IgR<<eJ^jhB-tmCYh-m_2?`bCYOoQjLw(*7E3M1~=4Nno>hkYiD{rrmQ%LUDf&v(OsaCLUozAd685o=<29-6c)hxV;A+3vQDDaM^w6qg&v~UAk^A}Qga|$!xt*62tm(1RyyGGS*fILiKMNPvSkwXjWCHys+LLARGMB_a+XWYT8WvFmerE7OiI>D$V%yW*x3{0+OYIVT>6BUhM5ypNx?dyQzvlhg-vGS)gNNwW*&GgmuxwyRxi;u*Ow2gia1J{kR@)4p(x+yhC)3Momp`YO-OK|A2*Jgtc)NNtiEDmEZ~iY{;84ej^N?cIV3YMOGUZ>op!(dZ1UjNn8+zF#ZqTBL9XaZj=M!hcP1xhQA;CB3C@d+&izB)7KzMrsQWzfb!p;ZLJFXAs?@x=ge2=LnqlfClC<BYDez(8DvN{ha>mAVHswi6vmx3=Cn0jA%FM9C3UlHUSbw$wKElDkJflJ}&(@I*v{pH+jA25Q9hZX2562*%UF#~BsLG^Bt63<^47jueJp0kRAfk=gPvK1&A!?2pH`*k7s`F5v2_eF0=jQMpfY~)}d!tLNub)dXpQuGtOrQ%(qlq198F_i>rlgV66OXBYG%PZ~9gyx$`aV)sp(ojv$;C+HC47z4Xi}#!Y3C`6VNC--vJwd^*3c|k4z(?ZIVYJgg*$LQ=AvZDK6@`23Rl!4!S_ng9gD3rBu}8Ur{)PqQc6JH-Q^eVwh+9V6`p8R3sqvGq7I90)!A4K$Sjs!Ql&^PV<x}<TYuGHKTw_(S3E&>TuchgqNV(J<dsDTD22YXDO>YGw@plavJx8>3z60ykuQW+QK+yGSz!u`HJNHrD3*sC>Xt-&aHL1JZZQ(&Ic5X$ShLAtu3axhb;61z)^p73uGZ%4RSQ=lfIfS_w318qMXBye_C;x-<(Gp(^1$5YUQ(<|;1iq=0asp&@GOB^liZ!0j-ns>p|r4JEejjgv@lL86M&|t+S~%g!cZ*m1i>#~rgR0vT30Z%Tmeyu3Q5x&Ln3Sjxcj9nhow{9;jm9;bwKNwMeiyO?C}E+r2{YLMC7VE^q-iACZOOUC?8oo$Q=>6v@oeYgIAit1e|r|_!H9{4^-G52gxGzR&rrmRvT4T3p=Y}>Ke3p_Fbu*&ZqRKln+o;0W!WRQMFKRbYOQQ7`Mt*pC>fGAhC(w<9$=>cT-lO6J{22%CA?DQ!<c5i<J(N>zeXmL{$`iN`*YBVk;k^to7bMh<WkxW0%A_L;ISHGsXOwZoiJf@J$I~z>Fyz&1S*_d~!l><~W<z`@gs`KF><6mUMrTwA(4X<_@HGi0lPis?uvzJLO>clirO{e^Z%+N6*obe2)J6x#C!!mm#8hiZ=m8WrkT7F1qpR0L|y+twY(7DqEfi?crxvIpNP`?hg`kR0&vWK*{Y{D(I-(7NE{!Ms|1(F!HcvNPM5n3t|`Dfcnzk%kPgkBNL?Hxm$R1E|(b;O8P&XH-Z1&k+Li25Ge>jNP|*@;zGYlA_=7UJ<};m4=?rPCC4e`dWT$s@>)}q<Dd#8V6aS=Z25>|<n=p>Orqudqj3=75{qvM{?Co(kHeSbCufo$t22q{^8d%<NW%HQ|Kvwfs~<`1%}Vv06p7=W^4wp{2iM%Mnl_e+rM#&x9FJ`vhTCx8tu)`2!*95+A1@4tU%et6hu?-OET^;~b#W?b1dVPuo4^*$ovw7R73V99bL75zym&`LtfO6)JK4jkRjxF<JZU_bw5iMtdD09y2Mu}B3^~%+AP!86q(}vhZgF06mUCi5pLQlL?t8C_#Mk6lF=Zkm41))zI=Fttw_K@Pnsc+6MGW!BoOMkS{;(b(bm^IRK<H96898k!vIID1iLU9}S4iK)bLcX`vjV+g3s#Ajl$_m!AbT40u+On{V|dhlH1E@vKnyzMpO(QZRd7o!!xo=s?w5KDDBz87g=rhl)Vof}EtPtucFI1f2%H+HRJ{kP)Mxea{8FFp?#kEw!97#|aIUF^%PB^wnLl4bCVJjrgO{U7PEL|_C+z95lM^&69Y2d&yH6!wtPrh-bnNBuJTjlSM#EZj!~i&S*o+uF+N;TypH8E3$EC&|T~man%H`!!fiZPs#?ylb*W4DWJ8M#1%YF=bjC7ig?nj?#@}{K+%e`@Y0u^`PqA79fT*frviK9$XCb4RdV-M;GsB<E*KM#go5o0tu8^Va!TKsdH#ak@|3a-+8KKTyKy>OYVea8)EGk+YA8(>(91_=~=c#|9boB!nWp&}=|6+vOskMc6JHD^BFi}Lx8`Jz0tyePFJueA_)^JoDfQ3x-*QMiZyuX^Q0t;&yFr_p#B`jw(W&^$kyxDW)5^&&&|*vJs6%LNjvfBU~Wq<qq6Wuf9TTt><FOSO}jOeQYq{2nnpLK!^xx9z;bMmGGv895yoDwrn=GyvNhjU2>TwN|huwVkh{r8Dy84idW}=i4ZnVWSMXtfYn$qTsiPJha{VVqT7puU@@=QES8txJBLu>2x_9F!iP*TK}+-7xc#UuE`<M=F2!NUf!SyLM$jw-e8``Xg~IB@rPhh$*O6qnzx}5MJ=eZ3=?v=TdX7hsGT76TQKqN?U;PxK5?7EOK(1C8(pRZUS=75Yoo!-Pp#}a^4|rM^Uib8;JiR2Ct-WElSLS?o+?i`SDonn92<V!*VJt$Uvh&pj^lCBt?W2O8Y{p+mjDJ4rI`x?YcX#az4znnm5|w2HX|PKdS~xui$4^4Tn!;C0ylnoBfkCRT|||hk02Swpx<Ke=|$8gI?RB4$Q(V5&A38(P%n<7ST=wQZ{wq>KSnpBd*~VibBc~Ug!%PR51LW5oa09Va{`7zR<*qiFSr9TfF$LnyR+kkp{uulXx1;RY*+BHEbwYhq?7zW7}3DRXO6za|FT~Y=%8=NFYH$chtTK6z00l}+lE~nYRvvgn`Q2NKzd>yj2k?t1acDw=qp@lxjM0-;|gz2<Ws|8(L-XN$L`2BI(S9p2dT^l5<A1tXQiegeu_-nh9IDMDyz6az5(jNwY=U{RB{*xlL>xu$L-qiXG0Y&lkcMR9dWuq&>T%wX=j@1nlUhG+rx*kuNFo*aJ9YhSg%tvgKCN>XqPm6j3o^#ElH9xH8(D#{tT0Aa?ok)`{;ijuG`+wKpXnCNrVETXu~iXy7g@l4{p0bLmZvqe$X43z0KV7on7phDodM*p*8jIlBq`=9r=EfWf%@@I*T1=ev){%zNDM(LbYi(X_Jz8!hZ=;0e-D%G~s?L&YPb{J0up;!L5l>ylhKbCcA*^EmNEjK?O4MeVgO*j0li3R&iXgf2v0%|A3npv?B?Q(|7{ED10M7{d(uq+0Lh9=hIjFpPpK53?tuwqM~FaAXssTS{i}-Rx$#0c~=hd(B$|vMf+O3@EGSi=j!;h=bU!YCuhCdH3r7JxWuzFQpNK-DbFtRZK;DDVbfFJ8@IU|YZR1d_uT({tF(gzVX<K!yyv`h_e%LAzpk`<r&vpQnM_LwhTzYEz|l=02A}w>&gNwclS)y{AnOQHQ5@U`bK>z0l!R3VRHq~Bo{Qe_Qm@Em08WF&m_afaQ}JHlC*?t9k$H06Lc+l`c%)lCJ_iVVNtR(IX%=oA*q{UgTk!=D1PotREG=Ia&_LU0*Q2+kRFf>CNG{D{g=q6UXS0B@>_-)@A4ya|my4xJW*p%(%Hl2jV29^u;m=jY6X@WI0?DdJbbmgIpdvuWU8a+rFI25SVN5zM+9Q-gkd;qxyu_I(#HBotcG5=j@VFt%!H<MA)WA!yV4f(r6m<wvLV);}s6o+`ss#+zDP$&&>1pcaL<tu0&@RJ;vE-TI$Vzyn^%dAsSf_p6a^Y)LR~oy#Z>U-+>HZ+A;=tcwZACQF)~*UtMgX(}=FLoF8pLiwF+?Y8Y1A-}Rjn-zELvOgEw##i9Efm+D^ns7fy7GoU?7SLT5SZLTp_DE86n9VBpH#D&-#~Pi7+JR$ri~hfitY}QJ3(*Sy|kmyqy(O2dC$Uy^}%rP51bu`{Ja>GC?mu+RNo~4&pzy{R!b3+=6g^BDCz$TcqGX6z5zYiz#E<KgmQj$wWU%Ge1c)KS?tmlQgrIjF88)cce_fUUp!vc!%Q*YL%bQcPB0%5Z$l9D<*sn0J@u%GeP_T(NO2!FUR=&B)I&@1s7?W2uQMk%lxTQJ06iJ&cgtEE;O1pDIzG&9*LP~WI2P%$?D{R@7KHw3l{`#Ij$;jTo}5P{-#(Dvq$;{EX{$WNPQ+tdzP^2&g6v&j^J4WJDu>e$exsCd1<(9vvI%L#8~PaPV$6UMJ@_q`TFEmnrWm-t(4O+S^P`*Xx^=UDY*|Ln=z}@f?ryBd0BXpba|Vn0E;$S90gAiMkNK`K!^1@VMvwnPnnmiDFcsjdeW@g^wR8K!t~?{f)kl)%haDhz97k${G-QF9nT$S-8aWa-K*pCvyI<1F1km(J}7}?l@P`8@0@e$1eHBvffL&Q=ky8U9DuKG@x@>Mz0>VqIenU;ll|&{|JV7)Ug&fYw_7Da!ZaWOBb<P83fe5w<afV!a;LwQY>dDD?}P#J+&5W^|MTx0;(zG8fP@BKOq>Vv8Gh}YM7O~Rm*`k7LZptc-~M}k_{$)9%Yx-U@LwPL!<6~@@BWeh`jzj6>69J*Z=JqB^N{p5a(c6&KL%}x+uomHg`B)}ILGtFvKasS-~2s4{1uV`ol~S82RJ@$>!y~swTp|B;{%Ls&eieN$>!NDkd}o*i5eO_fGDCc3~te}`%ZraRp#8SChp5+BynjP{1!w_F1;}LmXJ0d%D;N4k1j0@L6Ue!VoFc1_09;Qi?c+tKFvOxL*9QE01ARVrJf|-$A`Ta-OG((ndMbU(DH^}<|HOfmG#+|<KUe$3Xz=HacTRVFuIN0uZ&0V<rCERtIrsh;d$as`~lJvqW6PoIt$AV!?NTtZufWx%^#ri94n5-%kH=__m{h~v%|GofCUV@CCA=4V7+M1ym!GZapErafN39-d;}4hyAJ-ajel=wO9U&@@lf*;EJaqlOr)<0PdFwS07M`RaI|C)2I;DUgyt|r60bjIx<mOX$<&pgCvOGm)h^=bSKt+V5iERg)3E5~7Fy-@c0s|mw+nXr{a^g`7Sjm0NJigv%{XdI)mcq@hI?SW#&&4RM>NfkVCp$!PjmhR^94=Y9wi?;M=|gqg#6uO)LaBtEu`h({PYyj>Wl7W|M=`^V+td_+EQ~zW|l;sAR;gzL^Lxe2NQA^X%?L8EhX+NS)3JzyD9AJj6Xmac?iOs=UBt|Xv0`?@YeWmm@P6o32_`w`~eah@SM~#Tgx#5A#$EN-~ak|&iR|(<(uQ)FE>8R>|DSdgFlUeae$p&$j?QXgEW|z;}RlWcpsx?a-wiGMcPq<`8uKa-y-Dk3YNgIUf{$dqzz%#oG@Og7z=j5rVB3}EEhqtT*j~+%;UiomMT8L=i9QIr>B7j5n9#x5a=KxvaUX8gQI@kWg0<U^br`<G7B8u6;Og05-^U-@f*>^@fZc3f`vj%Ew{9sF%u&Lvv98wf;7{DdFRf|_Y#;Bpu|HFqJ|J#@ngiX5jEtz?H6$b!!VGJVxjxk9|Z}H8Icn^J;*a|Am=+`JQDu@b3Q8RIh%bBI`GNR%Jb%PKSdb-{eSzvxr+Lcik`sg@bPYMt9nZF>AArCe#Rf&_kZzQ9wYEWpFFW1K*4%zduwj(lwe8Ktz}A8i$&7WY83jk!~<wls$D&^-qo`;cSX2()lD6vQ%Zx$O2Bt?B@iW=CCdFgx8Be5wGq%uqRRVuxx^@zUFDtIOia1#9+gH)z`Gt=#tq{g#_atyW{)hFCuughq;39t%0?4%hcT0;jFn|abg&Ejgz1R+H*wm4Yj?47nFvX51ZMNWY#FA(0*#702}NA71f4~HWe=@ndbgB2w^%EGo}7Zfhex@bi~w%FUIEyf!UB{1+$&65`*_Q3xe?06!_p>5KLI7!ZwMBzhpkfl4z$Nv?uw0V$+CwTw#dj}g@`5Wa;?$A2r*AQ96ws|@NO|46YRI?P|VV(iJTkDrN~K8)m>*;eAfJ+uPFjC_h_x5A(lz8bzY7o_fVts%5Ylw*n;j2KfG{tmgtfuiTHZ?{onj62M4zEeVY#~0ca#m2gJaYJXxta_blE7PCc6qPYH@LX(t=6qTCL%EkOk4H;0JhpF8(3-1TR0;Gf+{0{1hA6#msyo|~Q0Ms%JKi!cL`m8FyL;WA-kgDKOHDq-8(M54owT#)pDks#Y^GX+L8#$q+e6_J}5`lD#!SJd}^%eKFO<lzZ;>PZaCntl>1v!=D#RG@BN*bQuZfN{Zjf{n|XE=NJ?^xh%K7x=s7&^sPhD-f60bok}eOLx%q?FWd1dUW(hF<oGtcMt2l{qxtC2R-ND{IFNE+ABO|<Pib?d>O<tRbH(Z3nNJ~>@#))%RJ1vI!iAu)mq8@#ihFyX_+x)0<&d{Nu=n{morGI%#a{vNu@wecpfyGIZbR{B$>ri9!(Jcj!0mnbd1JH_!@8LM)h1L@dKe#>3N}18pC{%PJT_KE<tKp4n=HGJ=14Wcj--E_I?_A^V=mt)Q(H!Pq*e|<@kC%!`BNboHbvo(nH_|7YoK3CXl}lafH=8_3oT2a3(W8FEH<o2uou>L3{vHEXTjY!vTi};|YJeuuVw3zpOQoy}W+t<8dgS!C%8jcr0-H_;ZZRf|Xy9MT_P&$Y)g6FrasR=B0zlaz5&W-fTGboM2y8S<C9iiMQ^?P*A~|QrJ=q^)xt+(|nz+t~9;Y`IVMBmyjdK47>C!_z5!vkSR!tlDEakty1ngb&XapNe9$3m2_5B{mZY0!l^;CDt4Zh?3*^a)aII{QWD3Gg6rq1^I$1gz&_5+)6QO{tg8h*Riq8I^DNYh@#JW<euU*=)k8{#Q)&Q8A%bEtC;KZx0&3za&xz1>b@>{i8@eY>_pE#Jb^o|uGnY~Llx)Cj6eHR{Wpv5&g~E?ui7p;Vi?kpr&SwcZo|rSH(>IW~O<qReaimyOVXg<6^46dGNZ%;tKgRrve2$r&@_B<wr7F&5#waZ+5hNv?fh5voYYHvr3U46JbmuPO0BMa`!mOs&3Ar4@!l~&*7^W+i3&XOPKO?b|JN_06f=B{#oCD4`TuuLEyg~8&Naa!m9n>w$6kcExVo+7AuovuYqY8+VMRD)-!3(f&#Xz#KN13-hUbZh}VEUtmF5awRncz=ZK&EL4W0jpxl-;xQ%}r0NzAHg=)+$GjLlwlNv;)e`a<E6aSx%joh5`^41A}OC(!gTMF&m{JVI_3Xo2n^*6f#YTV&O@&%W!$mEZNVEdLn}iD!aD2HVrH~<7!a4r0n}!1}v6T5K}Knf2Gt@8P32gW3ImxQ~Zz~3ny;=1}_a5s#k{moLDB<TrN0Bwr;l<mDlkGLZos`dol7da||hawg{$-Xae$NAwIIRV&eu#oB4x=joXVtX8Ym0fBWlvU5XU`)ulFwGa5oBQ#KsQP8ciUt^66h@F3yr?l7B{jbtVF*zhUE8jlPM6W&4?Drgx5E=D(5g(8|A*_gnkJTNi0oM7F>wF+Fdw8<bj#z(rnG$2i4ondMM%OmTU*HLMNx4omT`O#HxnSvjj?@RV7YXQL06Y?YMM|_*M+mY~iU2QL7s@i%s!aZ5*cOhBcC(cfVA4&Ja?p60ix8HLhmDq9rs&{tK+jN#nT4fH1VB9LIW(Q*>s4=*`cm6;b3JUhop_dp0j;u$g9As%&DGr7g{<iK+5VuqM#CiaPFdhC+jgVMHmDXu6tOoJh|I9O=1$~wtLze9f_KvF=qfxBCbI+l`LrdE+KeKxVQy!YG?KWj1<9Mi5fz5i1Gz{HG*o=e@J9uOe#Ga;^Fq*CF!L4|RezrUHlC!aGN8Xss^n3k2L|OH(&M%QXTswvF@4$<9ev7$2@zs~ZM;UdQ15kaNTt>3cRPk`#N){|!T@Vy%JGq0Xt1{B3P+ld9tK=hE*o4W5s0NdsU|K+F9jOemF0yN+@fX6ut1t1RfL5F9iv^V}LYQbUb{b>+fH(yym#2xaFB+B<Q;vgV5qc{*J6#I_GRG%r&GU_(s$?d7`N<hlM=8j$dxg|XtQI-%5o^e4xkC>H@(!;EVfR!+EaYBVdCm7xv<%01IYZy>q&7Bm*r!R6YkV4x;y;qX<mcF6a@f1*ogE^X^y~T_-9Gm9@fICLkoX4n9L0$1JPOjt9WJ&5EYZ;t(0n!w;I=wGpj(l!YdOcYRtj?tgd6Z-QNbKZlHloyuVQ<P39TyPgn~Fpaiu&6uEOOoob7E=?`0=MbA}vo+}<uML|Kg&93Vto9vt*%FvpgSr5CcV%WUbGfQiw{_W@6wq%IZ*2&F-4ef*%^k&<>nqvuY~4_}}3oRi+0-pQteZ>c@NTpBXO`q9$716<i6qYqQh8%;Uj21#K7L}V5bHaK>2iY$?K@zXKHFF=>Ep9Hsac(X;aQwZ59oTDIpwHy{m1ScSSA1>aKEMJE?M+2RcqQJJ~c1O;pdPH8e{Squ`Jg>kiW#&lPOTf{9z%RE&lB);_*z*Zgw!Z>A2B({B5=liVM7Va>;ok_@bm1I98T%>rNis__3c+Dx<>la{*FDSb+R<hA;#KYX3&L8GqAEe>i=^4CK&=c=8R+HGSK|BQ&U1w`(c8|RSdf-^i6b5sNoP-12~MU>OA4uT->oF>3%SZuE~uWNl)SDwgM1A`?z~JnKu}d@6pXW}4UL=X*Wz+^J@&_{COd9uRhPYhxVCIM{21!8>z-82b=mO*`r7O|e8H8QNfBsm+3>rLu4ekGqpOo{u904pzgF%sFPvV*Ezev@T>=+U6J36fNELL=ci{e~`5G@sa}A*pcljt4S6se3bnFySp`ijz$%ZoJ_^zpLw8|Q-6bOlPgrFJu^{MrD_*$W>>rL`_B8^oCm$ie@n{ALkE17umgEHC+@G2?~jSty4_Qd^i_|-k0;o-|C!>_&^#$V~IlCWc>9>NR{rnamYxUaQ!-sdMd_HSd~Cor`)au(&^t%wLgMHLYtIH)5c@Cu6*`kyJhY_VJhHRAIlR=2^DDPpi4H;oofss4M3j1=SIKaB)OvqZ8B1HnszZ~e|QO%YfNqFE5mJzY{=%a5gb_HW6#zYK1bZ^U49@2F`+!G~H}I-+ZHW4YKiDG#p|=y1lcj=EwmIa$5aTCP-RRJ4`K(V;ZhoxAVssw73y0@B%nE1lzNF<DU&81(kgzeVd(m7>GQ?FYBhw4<y)j**|-(@_{Dexkwu+hA_M-60ZuHOR01Hr9TdcD~rH<lTSg-35v1x*`zX#(@@q@bj%7NBHI%+QE2fFnWs_M51f0SoG@0wrIKiU0zgLxYqJH^u?wPQ;#6!3nY9|l%M9?mWncSx3gT7TBbm%>QtK+x@R-FqbO)?SO{0++O&{o`h}><R0{$LTP~X}sJY*Mme;SAtfK4%RgYDV#s~LKdIwj|`B~3-d3@4)Ov4^cnByE%3+HiR1BE;$7Ey`Bd<s@O!DtGlyQ6uy!l{=6U=edPDr3?!T2Sk^-)W;e_z)x-35PA}R`HM?JC)nA%E~4Qb|lqICC}C}*Li3x+!dVcg)#JT8*!Ccr<JD4-~A7{!M~q{hrTTD(AGF9cLh4iz)TF5W;<o+h%AY_+NqKd1De<8&z*Y(#JNeE53c3YHQAuOv6L>ioCiZh@9YvKEt39}WWtbKw^C>R)yBu~IK<Kl_J9=Z?Rd@h&NXURaC`HpqC3z*h3U28_;RPx3g*`WUo~Qh&IoHT#M&5RO%^<bG0A9{)fs0oGU!dSm8_oCET0vupOzL-4Gb$-LM^SKrUSDzXqYXdX6vY(g|xE5ud<YCGzL41smc1KL3W+>)WU*lWkoGpQVFTo+EMLosn+&Xdz)&pb6jBD(Vs56pKD_XkJA2XX@@Or9%yZD%iJzwfQGisb!dRS-Inm{m>4tHp32USTi9}mY1U}UB^|C1K&d$wAN+$&r-Nud_lba^GwbH2U5qLghFznvyb?Xs8F|fy-b%(^TZ8W!M&D|NUwh-PwE;Lc0`GmHzf6{V!NwSD;111duCzABVG9GXt&!NqP%JkV>o;LzG`2Au+ZvBERqyvW<uz6uUS`VqpFj>cP|YpuIrjGBN;YJT9ogQN%-EBE{`s!qPTAO$t?kNY+p^idY_>7$?aYR2W@B%zV!o|n!mVb;HEd+{$FLD~XouN0t+h{Avr%i7vavpY+Pk_uKIlJ+GGE1zZedKvq$(qaiSxucAa)iFSx{MfD#6%bX2;9Q$@PI3hLu*Nw6p70^vt{>y|rCtamR)<mA(BjagcG|zJdtlM?prT%@IS5njQap#AK-nE<f3_gRLce7$a&7PSTHN@ewAn(qHb)@<`uQCzk`Ws%EYPL1A@?b3V5mIxEL#9{Q3gZfH4pPFN6Kp>h^nWrKY6P*tZ2CgLgSGq-?zJc*6Td4w_bi>}6aa&as`;x#E>rEk1mju@kjJ+rgt7WMqq3TmEcy^|Fyvx(-ROVb3NGA>uEBBzitrbqoEQpEQ7&ANhPej&+rLK%L&(J`tDi5rB+sD`wUkNKxdD0-OUm!quy%nVl!CfQAxurfA6rOigUB))?S96-?;AE%01=J{P=h~nnaaJAS&9~bew>C~HNS@Tf8A>fE}a&oGSN;#?$Eg(b*6fd+#<`*vATdl_js<Fk9CHGAJaLW~HmaL~}$vuGaZ7I`Z+hTErJQ8KH3m<hMds(HmU^+ONlaNvQuAKys0c=1THIACn5prP`{ii4aq!D7>16dhr9!}CXVTJVRYODY(Jmq7`<wvcb29g#jxJ40>9r(Fo^BA(ih>(q#fLvawTAtxXof^9Uv6ER#-@!g)V-w3LPEaApW84dZ;_-m#t;xt&tVbb(<aTO_Ov9hAy#Enr;FS$>JV)3C#b#9l1oMGujPqrB8|lV~mZ@%#2RYc=NhGSy;4wj+FYd~d-CgrA5z<q}5Z##gf^Z_BlU$l&R>hBLCn+f<qxynyzhHw5U!1=_JM3N__v&Wi(jvwiaBwu9n5|40-00Pm*T8~eQ47qt(XEN*x46n(h<Pf*Xc(s^k`tHkWJrXtoCDj)bLL8YnxLxX>$Bslucg_t<Z_^!4?ZBQF^b!ZRXNbz#4eAjMhQwH1bJ7YBRek_T{s}f0woDYwkKhBRfb+l*#Jy3)JSUeWhy1g#V&;i@kEKCEIDW-bw2kdnPcsYHKe;f?`AazA0npk;>q3y_O{a;W*SwPY{UGX>=q|5NJdd?dRKPOo^;*1thP30y#DeQ$(uk_^p3lgHjQrKAR`hMPd0V#8P}{eFVn?J^&<93@<&${ez}?UPLbVgzOh-2{zXr3yjRGN3QUmFsj7K}8k*46jC}-S?X$Qt(70I;BEvB!*`}y>wGJ2W6%T#QHe~VD8zO1yMCwy+z9GfBaCXF&!M%aX5%(<U9^BSC-X1d_IAl^~v9ya}mDe|Gt;fnrO`rg#>U)4!b<YmD=|sBQmgBa6g~WfegTc&OH0(^oY231ENFi-*+^omrs4j!xX_h=8^=XC`gEg=wE#aSFE#c(+==h*}f`r-E7bkTTXBYC|{MtE*ZlTb$lU3c-7xqRSx?BO<Qg?fc9u*x)3_&{eQphuc6E`7!U^IoQM@|}{J3RGctiT5;QqK}xO^`1O4rymVWkl;h`Wq5&g(|ze(F;%I#f3v1$oB7oB!JAx*cLcO$`M)_Ul=<?YKf^%Ms`fqR1N~U!3-4BwbTvzyhKW-W%=Bg43MB$G<baiCLrCaXb>k*EYf3>3gx!b@?FrBiNq*~a}62P4qUz@;5L(krNp%iODBk$fjd)z6ArIr+n}3<X3WN^DFH_Mrj3^PO+JQOq5hnzzA~Xb1?2XfZ|=!)J$z%T+@w&|@LsZ@lhU;<(`A*urV<}5iktw34?;5aAUg<+BNpCpCAFYth3Nn%T}-lAopBu+1WDwW3_SCg@U#0NRVG|zyVl)e>i*&PN^vW}Nzg5X>AZtxh1WM#)wMZEOh`tq<GmCTbOjT1edehXiUh6tqp9U{E?X=m-_G^^-tLXLMunXKOvs(<8XIkI<1#DwG;yhwf%jR<`Rw)l?Ho<=S@VG@G^_gg{x5#F#yrE)JjOwGa`Nh61Ia!=Y|i-cmuUFi=EJ8J>qo<4;b@#oN2P%WM0^4oJ5R~TP8!Vo#A0~UF*J>5t|(<tMJl(mxJ}Aj-R{x8UQzw&Zuw>Y^0@z}bqnkN-YFG%-Y8|IWW04USLSAY#&(Zo?3uT6hCce#7vyos{kw>mw2#ET&lIpDWt{H7$`5hOtlUKugRH`xQX;P+6H`(RXI4dWj}gEIi`WOpSo?<pmGG^6!j}l$g5)fYZ6z@)=PM(HR8+RF<aa<EEhN}mPc1*{$T7g@fr)9NuMyLd7No!^(a9Xs$`+Bk0Ttak&&24_vJei(pe`(?W%#(LHvv1@Ar2$X-A>FI8zsff5V!tZ#;vnNU^(+pl;Z`+>T-Fxuh0JU?EIH!cB$DABT6t`b5vHB68{ysFQ&MzqBn*fGeChDgcm+}y1T3Fd`**i-PlH<Qy3x|{p$GWmAf`KqfoJbH{#|#?HwM!KGn>wO%uA-{E3Eh8*5%voK2@FlXE-BS;oG@2}9Y(R1W$V%9B5sF5@}h89p)gd$GLTnFM#VL{h?yFkIfEuUJ9sQInEma_!laU{g9Qez0WZPoI{>ro-Ngy35S}_CN59=g=Rfn}|))@har`X8Vp&-^`hjE8x3`BgC&~xghn{XPgjy-lcEq#b}L?9A@SP*eC_bD*Sg*_|9msL~wsK0H9Zqd(gyFSa}7BM=BP0;b;k79};+OE*OAZkWDav70<EN3D&)S0XZA{lE$v&_7bFpVLz8ke}?2nQl9Tsw3I$UP279Nc=4H^bskKi10_q-Qde<3dp7Gih@>HT6ZiW+`%j8hj8GR!(pu{kx6?o0<`plPI<JsPY2+dKGcge~#e3MK2s)C5UJD@4^T5bRcZE4=aFfN1G~LXm^A+mT!bjWyc%pggywiYoVo+?|m7GL##2hp4e*49QsNW##SA9Kl=~`ymIEzw$pCsnVs@^yh$3cuvvidk7(nL$0p#~KMF}9r(bR|IQhFC?YL^8ys7ea4@?iMa1T<$#fF)pJ9+uJ1y2$=5QAvqVO7(3B?OJ(D1QGe)`GbFxvE9YGh(FZTko=ZJh?y(cY>t@lRZ3Nn5l~BRFFeBO8ht?WJkiD`9@~YQ8xq4Nz5b}5b$TPWDKEmheCSr(UM57aC7jaB)o*<3~q%}ieXNtQ!*z;8q8BqjRFkYFQ6hhqzA?X}>F)zF`(H(;*iJc;Hf+*?jk33d_Y$;$8+&L>>Vs}x}9Es@$(*l~(j;7To58z6h4yR?|ya-sCFvVfuObfD>A5j!WW&o$i*8w97Khkbnu(Zr%-YZC*Z%f{e@W-W3w-rW*r;@hB+&<HJ%sg#tUad0FZaaHzWx_GTQ<prR0t0q{)0vTnRept~RWb1y+~-fqFvtB{@)Y41q3qX}AFQyt(!t0MMRp)N?8dj`aAZ~?x~QU+KsGU<L2*y`FA+J>JCUoOy_tz0$8$OM-ZKMbE^q9N8gpLBbJx<+6(qqtNxk_<;b_J$N{;Uhq@uQ*31W1qEFZ1Hq9i#;Dc&mShLMI?&=YPO#&<M3|2Yf@yQXCbTXkz%wfdQo{#6_62~fJN^~cyY0pH#cK)BmgE{N#mZLE<b2*P@bASXqHRwAJ$PD!OznXpeOst|O@(Awgg8;+2brl*D*Sc9-yb|K2N1LAlp6+yuPlI5&CCOh$#8fBhfX0}dm-UW^>?W>OS#jYF#+3Sc)bb_y4!8@%O;pe6i&U(GWzSF(B>YZI3pP#u}uQ0K5_X@vFx}3Nv_pHF4#OFv<_rg%EAc)M`BDaew6qXF@^d%7>NTnw`*>69c;71p?QdDd|_0pwi-C|)=DIS&s#u<pq!pJfKhnMgdadaD(UNxkQNJ_($j7KR%QVe^dqKcxdSSj>YgF!v|yzad4r${HnI$)m{6<9F~!#hui!Xxv&ERvO4@f2aGY!-&xg@)p<EUJ~POg>f&MiE`ahK8^jBw~6160<6Wo?=N88k=1xUPUza^HRc|ht}rs#39>{1wkqIc~tP-Guq4pSwJIcI^HObl0^ATcVAra2YlHR4W!rRp3Gg)g_9ePtccZnq;nJZ^g+(9p{;gBvozhalG_87<In-C{nD}{%A`H!c+{z=5#J>qz9gDBe>KgmJ+9TZAFRUC8MLT7EPWF?&oRZ9-iWQqUXy^J%#~r_w`=6eC~RJpB!jgQS|F4oUkmpi8~E^p`of#b-?iRA!QH$p02#$K`qzV34{nRyaB(M{53V^R%yqv1i{DyBgjq#{Sw({3b+4aO+MxN#jj+P|#rF0wLdZDv=IQ?SHhK985-j16>eo{HI7u?Z4J47S$*WD<IZknEt2yX`NDyB+<H%2FNz`}fV;*C0{?r5?F!*n@@B>h*6r<6CXMLJ)fmi+C6z@G?pym+*s(a5N89TPfLdqoaypp8;0%0ps6TrQIzyVCvi4R8bo!i(Ga*kv7P9&xH^p$`(ZDx*`Oy%+H87-rzTV<_WcxPhIsK(cwXSDFoX%{J72Tt$wMep$N`0S|ma`J!c^!*v+ry4oE+0Y-4aVWtizPZeZ9G>O;)!ySIFNmFFBj&}yDbmmkTEq(io%7h|tHUEk>F3+RxwClehUjj1umNvh4>2?tt-w%>V<CPYrQX1xqi2({yW8>J!{C?QBh-H7$0qL;)@{S`frswVqHvMIYbA$fem<8RG&gcx$)SwcEdG5!w@55jddHRP-5bNJxY8-l?aNU^>2+Fmc%6EQm!=YSm+z@e_T6OamFf{R6;;mF%xvQ3m(IZ>!kcmSNgID+ow!dkO+MuH{?px?HOr=}qvXsC+pqwYpQhP1S#f&P%$vFe6sJki??ZV5JjeXvvUhRbKfXG@{MtD_yLer<KcXZeRv&YXI%Hv+MaK&C|00fnX<%xbM3WTL*klFumWg{|;j)s&>G9;BeZQuX()M-$3xASxfAW@%<SCG1SV@U{Q3tjWhQTfF;?Hlf>kJOz#sI>F?SM%p+z`d||26S`M1vu@h#NWA-lkaThT3?%$7J?BOq3`Yi&R^}n$p2EiV_&d!8@m=^?0rXUkqr?J*+1o87g4JQ6`|50*s-3*FyTfAbqtQI<GHJ1p4T{#&U%7&yFvcZ<yG`X%q+Ff<_q%x*{%O$HaxO>&@6xO?4NKj;~(5eo;$}MR<4Q0Nde!!_bvmq<SrfgJm2N=tGSLvPnS>xL6KD#OvrN%%PN_ja|5=QHU;ON5VI!X}U=EpFAN`BfWU`1j#=!Wb$|t3zt=4v&E-Em(Cmx+C}BMg4o@Jp%Hcoxbj5+S`A7o(WL4s!i^~0+eirv77Y~(*F_+>7oqQgpb7bcNVq*5PRt#SIrgP8+s*X#WD(5g+AKl`VKgU+1F|Kx+wJP<mGV#{V~wa0q?{-ph*=dcA4t7boEF%BiAbF^!jAo@VcvVSl=KG(HDU(|rtgAi34ZcOB2`D8APE<IMsX{3f-09&$8f$#`B~m*a=cfVj^$Q^WbQ2zh=P37DM9B-(t&hl^~C(EG=C8NG>TbqVB;k+$c^zry{rOtHl33pvS9=<0s4v6@K|q7%J`M@QRe2>IVaA<rJRuzW#t;ze1+Frb>ZZxUOP*7>YN+cuNq)w`nq-;ocsOX{3})jAw<cc{U*yWlxC$V9+K#5$9u+0HI2$qLYg6R*_cY??z*bwrqTT0|1W<jf&v(>O(?%=N_ALUz6srs8w<inO0Pu<7UY_od3_r!h_H(<3;kFO*rFN(BTJ!!;`N7IK)iO*kYYY&QFA~|=v?c`sA%p@<y2ULt&qw=3*ous*|v&^N`^x+Dr^In*p{WT`mn-j?+&Wvr5{v2^~s!tVY`Zq%AUzj(&<mq=}*$>TGHvGOl%ZUfp`2QpMJFRsa|EVl1PEI#Xm`<nN%tP$B$hyJ$QY2**m*ppF8?j-K*FATI5xH4Ko%jqB!q)ueef-W&EZkJpLA=?{83IhEX*x(f9J=GBilfv<U?X6;1afgN<Bhrir$z%_GUN?Mfx<n!LG`Qadc9ns>JhLRrPZ3f@~Zm=dS1l=yHJsG{`as*+$<{e=F*ci;Ujn;@&m$0$oG%Q<yi1?c2YJ@m=km-+oj`a_^Cnrw%Jhx2J);C;`ku7@lgts-*%hwpy(AK63<tS*_&%lb}AHw_D>(4h;T_+E;0pHL?mK3G;V1lEY&d0{YCBqI|xsdvYtu6RL`MK@Dq!uaAURZ4i{#2OM#uq7cywtfpgeD~LX?%WgkCd8%f2nEC<4$NRk7X*4XrB75Uvp!JZXyhd`SuVgIj>|tIeOr~D=`nHRf#Gr|H|ozSBt~vkL<w}&rog+!`=GiGqBjwDt%w&=>_dtiXF1ngkGh-*J};*hxH>-VIj3Fp$yu*fuY&J?^Y`klGu{Q#w{1t?+n7<{lH>;9{R?;mO3@vgOnmH83D=fp%Hom<pc4${$pR9uPm$bM5*0~8qp?HgLM!Cc2e4)f`;?D)FB|u<AHMsmf8$UaP?#qL7hWk93DK)2L$5cbBVM`sZshqLJ%+R@=`f+e<Oqwz>0PwUc!sViPy!}7I`-+HL`oQkh=(I@j(z#4mkJpWUwH2LbEAX?NbF@BoSq-{PO7A}0#BE3ICI1-8vEfl=zvCV;fzYTuEY(&2pnMP-bS%6rn&0V?Ksi!SLl<(nE8R%{VL0eoW3ZE#}bi-O+HVxKQU|1#Qo-8SQX-n`Hf-|)iV>?m;RO(8~+50>MZZybYyKNu?1vT07x{p><kTJ@-0f}WLYw@L7)atoaGi(Se|!wpnmn1-ZomJ3*G_t2qP4d2e&z!V6o@xn^Mh*EJtFsvUM!az}ZkI;09kww5^UELU&RNz)Ad&6oT1wbP3D`(SkT+cbxl&vdBqEF3!R(gCd6H6p3<!sh6nD_oQ=s>fa?(?|T0iH+7_JrGx6SdTM=9+6j{FQV6w38qI5kcPqr)aPw$~BmrIsdnnv!A1hDbEc99>xZf9We!z0xJssW7(U?DOxy27JVM}J-;|@@`NEkbDay~pmwhzoK;HzPDC)Mu$=f86LxB;znLi$TG0?O%Fc~kAT{wir0v)km4dK}|TX9MX1n)=-;(cT8$QqYy*uUpT?G^S72Ko?vqiIKlD3cIE+3T^UN!wOIU^{NRn)~&`>@FgsOCp^5=MY+t|F5ApOx#pY67pyOFft`nu=>M0+;Sx?_M<^^zbq14N;lHT5(yBuR-e8r_+fZ7@?JiS9F70M+d$@5MOd!(sh!INcsJhiX)35Fj3D1^mBmck$W7G*Np@;)b;1|t%%BNrNd^+3tbnJZkYX8$yWmK^Z+8XRh+uNsv4MAk1G7etcmB38xZqRz>3&}8-y@T^Ny-QAct7|q{5-Ux4EXoUi^ZWnu55I9Tvqo32WZ-ZG?OoD2u;lI!R$<?Q{|#Oc|6;D>)6I=tN+<wuBqs}l+`=JH-?h9=)V?q4@jb&(PuuyqW(I{iC)ZcT$yEN1MQ$+ZVFTm`I@YYzQSEAU%9z0B1v@|7>F%{z`x+R&<C#~|)gJSVg_k+2qc$6IHgln{KP$>!FThS(4ZqA2s~Nf_rj#C6KOk^*4l$L%n>%>d0}Nsf{7{fk`kj276yaIhLE@bUFH6qCj}xT4LhRuOqX%a8CY)w4Zsm*u{b6;o_;kH@zTB5?kVe>l5MW@RXfo^F$$n|s=cwd~Qb+iEt%1k|?36xPYcPbv9sbW&O_?;CTUOW5<bfr~qrd&n&MU*Kh~wI28+EfwFt+Z|C_vS@=P>o5Wj#oaPWKFQKQ!G<Au6*gjE4hkL)f=E41@cZ+G!(CiQaOMKH+3ntnx|V+$otKS+@2Ew<cV(a5H0nviUciy;dUryzTS}=W^f{sO-y+BC}gNXXZ#!-LILo?dDpE0qseO9W0^ylBA2WAH?tF89JmJw<C!zqbazSUEEe3xD5{?5aqwd5fOib3Lfvg0eEYJuY-w=q-JAa6@N%_DG@XDf|wnJ{GiZPCLGoYDVyR`6`qW}qvec%caL^I8X@>|Bm@V^BJ@@t-smwV6U)h=#Z|DDJ~ML_ItKQ1+}1~P3_mZ9p<HI<gB{4xppqR*sZt09S!%kb8=RFDX)Sgyshwi#{FSp?2R*efiO#$q{r(>ro3w!A4o)Xri^NDgl?L9N)_7x&-)_AHgg2J$^;PK^h^lMpmY{i6wp*9|R_#Q1*Plnr+i6Dsaf}Ohv6*_<mLsN7Mlc<Z(1rF!$66&6rn*i<LStmSaAl5+v1iQ{RG7*J#@b%7`e)sX{;Tt={-Zrzsmmx@(Ut5S`roRENM9|b$>z&iTX`ay<U%=<zP5XPrk-W_XzEZeJ)J1k|0?!4_1^i;(D&z*K#qk%V1^ZHC>gHRU6}l^2#+`uPP(WIazqE1_~S;t#AfyM-5NRo#tcRo#U{jHWRTa4bYFAT$pbwg6HIM3O}n&%LA<+vXsxpviczL=N5bM;20?hFkz!4vLjfPrF_7cloEwxSB<(eLcd2x{umGw#F*eUz5Uu)$oG3Z>!Goscd(rDYN#h2yr6xGBXjqU5@Pz{o`tLdKg!8;<>Z^4;;Xtc(DB#JMr3I&o@t`Sp^{K$84K6_9Uga6#HJD%FwJMELFC2`jOaedBqCz?XX}=`)u2ox<juo!|Oo3ZjSm8Fqh-dZ~ap}|i<<nsCm`D*<oaaN~#X9TyF{8$Fd(@D{_11|J6U*`8XZNuIgP6;&5*tMa@XWjz%4)}*mmZQpTYoU+=-~YHqI=o<07?>)+~B?zVlfnF+f!=<8jZ@@T2n5h(tC#_1e^@MVp51waHW)YLVRWVUa73$NXjv!=bx-}2{v+OgnO_g$Qez&`K_O{tF1rN7O>}hqRA43l^&=ep;CN`^IJnn$v$Y>3d%;2%ATrMd=ImbsP$x9vq#Vn!Q@l#{^+PSdwYycq5Dl&u&*6lAHO5040OZ?XUD=$huRA+@<s!f-oR<I4Piz#e1tn_^_qrugfHX6zH^Ve>C~kyMd(imdQueb@fy-zQ{#jToix`Q=iDYWuZ#gq9NwKn#~cy{ER2EBHF%z3;NheUm$8U&COa~`Xh&s>u`t(I3K+!Ybud}ZN1f1{4ac4n?2Bk|9T;Rr>~B88tR_J6$bg)M1xO9&y{9?vx&MB>^FD))kAB{}e+ak}n5++XL@v2&)M25lISW%J%pCSKW)P&2BEv%=iljLB5(JiZWtw7m{^3!Qkpq%zX3IAQbd&aHV5A|nR7N7y8MY{Y<2JYy@Y~R12fyUCjBws~O#Di+hpA4s54~fDD|S>L=Z!A4=q!4--u&gRYpsB6gHyLFf`C`mH-W->tC03yYaO&CB_hj-y<HPia;E3CvH&5gLshp7I$eOag_sGXTtv?GmGIK`o<7p{F3B-kZm^8~HEwaQ&Mk75yfqGyL+cth`RwsFx!zIMv{BYV0fq>ir-G{W2ZW%wdPSHt9%Lds^S7li&j@(zU>5Ms7rwoXF{N00vc2t^{e8rHzi;O@S{Ocp`8s3J<yUg!=YVY)ZSdi}V@R@$j7H&1D;PeTd7+e%W3L)=&>L12J<3#b9Ryix6uOBD!395B1flTR3`NRhjHR(Ql#HdPl$ePhRiI~Mf0C(m>?jTP57W~zjZkt@FTV9tVL1>ZZW#z%^xDupva|rJ&@`mY%q@e^;Q1YI`oY=x%DE>Sf3S}<x-YG;h7cj^9mrSjZX|+~u(AT-Gs__v+vMaCL>f256Nw~dNjSMjgq*on9cf+uD!Z_io>Hyvnw@?3BOunij#(>1FHzT;Q9EP$H6yoF{$3Nk*Bxs;>EI{ywn6Vl5=ZhUU8ldC;k+(QlWlS>CraKPxQ>aBSP9pfoHsD8GdWp);jLIe;t%c9N%mH(tN_!G%-fU$@nia&if5_wJgv9~?l2y658|oo_K=W^J&2?C77?}gW*&Bmr*-!$dOVT`Ow`TV^Q_7(<7QgRAJNv~thuSP6ru8Pf>nS~<zoNXfI;+N1dT@hu8Zr!ZGG5PfnOC-#HQ6w{Qz9|7XJ7EXh2oO2J0i8Rb7KWAoX0=Yxj?pfc`k(@zK)IkIV`DM@dG1Y%u(gl=MvyQQ&-BWb|E?b^Wo^&>sOXK3W307VLhao<C9men`@38-$coP0n`mk;f!)6pk~P{1_Hqks7VJzcu%0xzD;O#+umoF>KO&t5sj!XwCUR5ht;>a<pgz)UTvk0{84^8jOA7S!`%rEsKOXw?#K~pm1HP4IGQ}QgFKTpl;?OL!8vrL1J5<I0q-a?%C^$I*J{V%@qZL@t+X6hLeA+Q(>5v56o=HBLtxNaxqB#*@9evVgzB@=GOlY69Rqa', 'c-rkfU2h}Faqs*UjXA&~bzJV=hY>)w_QI2RD<V2cA+_f?vcMaWO>ypqGrXChw2C0W4@M9m4+eY=4hRq!Fq|0ia~}MVUvq!J{t4-?>8}174n^+XUhI9i6MMR=tE;Q4s;jH3qxmAu3Y32pM+N?%G0oCBT7<<cj;>I|znzhv{KFK7#WKTrCyYj662^CVl$W(KoJ?>w0$&>9OI~C+oD=vc%*l^Nqwx;f-{2o<esFs7N&m&mLHE3Wda^0F#>d@ZZ*<rnpnW#h=4dpHVmunPI%KSAe1n^<&LSiOEE<R1^RB2WTRla=BrL*!ePpF)-SZ<-Lslj=!fZSv6dqIhbtYHAHmGpcebE!7*q8=+(aCW!T7=hlG)|Lgblq$q@{bi1Q4!<)pbN%;dN*mjETS|)!@In|^PsKjM+Cxt@aNzB@|!>X@t5L59NwkNVn4WzCYThp8YW8t;G<cT7io59@|L5D0VP`|MKs4+RRfBviU-OfTHrWJ6oh3m%J3r1Bic0~R+i&z^LZ@!X5&em;3>K$vq;FFkb#lOX}0zl^;HSsOR?BHqOhs)ZOf?N$<o`=G#s<}P;Ce4EvuMeLb3$ZZ*Vl|int1MJi@QYMCBzOqPo^&r>xRYBOr}qoI9~M2iRa$itLWpWxb@gIjIQ-fnVYAvcOGQh5ieIK>I!H9rq5-Q4-FvR{qK0^iwhL(L5x~o@t+da?~62P;s}wq|Y6O`HoiMba2=kppSoQLxvc%I#XPXXJH(dV*&)bAVazcX#3z2P1B4H5k(0b=_Ri{jfmWh0TsaT$8nlto4|yQgwvb+Zwmae^fsBmP48(SD131G^5nd^+d|zTVkmGDU)(E99xg4)qzM_qMZg*aYY&=%7*TpPzgpt#u1!Q$7S8kiW^3zQrgfmrt2wQch^#*XsI}3gZbbs2?!iHCINXX58WDLB-C!szqe;1%3DXa_UPZ+WBVHBdGooQ9=tWc<Ew7Mjh;E}|Ml=T^BuuWO<eD`){J2xDogBx6Ab3K0pz?|8u{<aA8RbP-;0~F{W`Ij&rDGKE35li}5Mt9LX@O1%zga9Ek>vvF3bqiVU1l-Cpjih6S~qBEtAqa|T;OgG5NB;^%^+xXh;<b$nsOi%bA^tDKOGdunNCxZX7ezP{s~W-H(|Uimp}c-elvPz{F~8VCr)p1M*g4ig5W6_4#9)9=@5;Z)A?%#o$IIw0DRa7`~St>lMgRVblDe<uUKth8JE%|nzRumJ(D4lOcBn7WTxNxLv(U_j!s@4A1iSz8K4L=LSq6Q5JVA?*D==T9vm!aM!xa+Vw2P&Ye_)YhYr|@Np^zDWvgLLloZ!+SW1_Ip=y+AxbzF478S5<l&8yVj2Z3PXiRK$%F|)d(9|C6q+uzvXkvBMf-8b8Nslm4R8?!85*Ks`*|)575pZxs50bS8%P9>hy=C7TLA8M>!sbc1$Y&`rKL{$LNt7>$p}PM`80Q#@D+WT=WoQH0rLg!BN*8pIQ=yH%Smp(*789d^R3d7D7!MP46_S~f@~bYX-UcDVV7-I-2^-cponH~_c!I*kqKzi05I$pK;U@*7fS@M|$(I?<&>~B}AhL5ON5XvXlyVD<E=(qXC`1}NCGmyOkgBaubgOA|FOmvVkS-Q&F4}a^^Qaij!hF_7H#nmtY$Li|AatBBY{OC8wMbkX7Nph@!Sy4z5lOxs_J#*0`faVCDQVJfsV|%tFyZa*6LnUN91O4I2(XsbNZGOz>&MOhL`Th*S0lKJ@?~7)#zGRMYl8{egljb|X>dKjaNqnUVCZUuH;5(_mwT#A2r1_mK}p9EQ!7kb(GOg_a@<Mhw1^`N>$l({deC}<tU@;=P$#Ny1hQ0V^ozt%EZEEtrVY4nCHw4z2#>r8P}--M5MeBBHTB7s4uWbBRb9-tEY277yHNDA$!3DR)YX5X0duPQ3)O_M<rvS>ctX|(={RTyoiEZTX$Bt!tkV%BC<SQk8+;3OTCq|Az|sPc^d8aOtGzhYd^p4voQD1hYTm<PJ+$0QSVIC>4^AOgEEh3uYJ_N;i@ky%w(+AuCm1-ndt`oKw9-mEbo0^7rWX|M9%D-N2q{oX^Oj~C#vv6m`7B!eb>Y0`g;N^M+^DDePZ8g<inRIpOI}EVb~<XDj>g3MXj(zf*R;qscC8G0$Ly41c+@{5d(gqB-Q)g0Zs*)W+rlg5Nd&?aXE+(-ru+-Y`W#3E`Q2+~D~Exq%e?~fx7-#SMj0{W(3~oKxx177(zU6O*lR#RAj_qXlNdm<1E*N9nv_^5I&l9ydh#5daZkNDYO=2hvqE?%RJ))Bu*;XzY4i#KbS`3?7}YOTedP-n$)>uj;l)}}hnUfH(Kmw;F%ko0?AkOZk1P}(7;_=lC%mr8C>6!jT3be&*zl{dKXlD2gI;1xC)Xm=p4F*2(F}&_;vF%obbie_f9nWQ0cm8N3OHxiW)(zPW#ri46Y_GJI)Sv-qO|m$2<8WN2be;y2~w^kMRw_1cbWR7#|A(X_5D5Y4iqxfA}PJ+%)6u-@(mCG1lKuJPS6MFl&D@sMRr{bLU8G^74x=hrP{8?b-U#d*6dc1s}n93IGN}@+*>R{O}jm#XKL-W?V4~mX*SVzrmnV}hI>w1fz=Sh-E&$FtcGPim{>SGV$Nn(Jr~AVcsr6<*I@|RN{*z?d_H*WH8qjjFjkIw$7j94cFut0RL9{Jj^&aqC4#_T@!d2SiYn;7tbDN(O?ECHPylK*Z@_2aVj^|gS|v~gxTHw6R-o;lbdk52=z_yi3y7)_OKY?&jb5RsstqOJt!Z#Z;Um-7`AdA~9Ggqhdd0eH|JTqslDd|t=EOy*0v{!T-K)qJneKI?8I}U3ux_b4TeP<9U2(WtM9C623|C(#oEQSq*5`Ddd2e!Z+s;ZH0Z*ltXPI+6JX1TO1}qa<e=&3H-71<*8g*s-_nU8=v{;k1Hr5{9!NF1gymxT^lI+BfdfnsmBXrO`K6oj1z*|u(<1ijC$w09Y4u->+?Bcc{zqhzrly=D(Gk>RAfx!!tQIu$y$hLdvS&e?_NKA+{I%A6<qlA2-fgT>1z#&*4D8cbM-8Rr0!W9NjY`Xi{zV4%ZU=CuH_#&-EPmgKsAd7RC0c*H6DGCdM0cTykYhHH2D_x>@_tAU$##?YwS);^4$XlnxPfC`yyCQ`byqcr0lEKOvWnV&U3)arln1xwrLMcx(Ql@Bg;oiyV_^f79FgQUdS%>-8o@uq{8Dlv}Up=rVA!f%ukyhNp&~^*GIVR$4Y%U26Yjfz@D5`q{tH<iH?xyyjY)E!t5{P5F_DPsLi4s!DBBZA>p`xg*)6-G?JT1Z)9mu%8oHT4Yx2RU<&RXv}y0t2{R_rck(e(`H#YifQdH4!!)mUkVMQ7#E6d?*aB*w)4GmRr4Fs>^sXry>;a9X^k2C?aq5>zu@0_w2e)|z6@Kksr{i5u^0G+SP+Uf7o3Z*~9ra^@o<D^#B?YgrqU`F!0KEhzRTMkOc492WUdIWEdq&({}KB?rCkvDpi{HdnSFDL|aPj~ZZEJb%3G=3&|Uh@N$5BePw!THPumprHrpn4J-9!Ey8r&gfMVB{R%JlzGz>9J-(Tso8<c#DLu}Ip^*L2)p{7*s)gjpq}|LdFF8_1xAlhb@384(}6uthQHBj!TXo0&iJC~HSn#pw8+QuPw=(0jmX#XPuSKriYOSnwC$pS(D)h^L>Z{BQ<qfM3p_RXXpIt3R~M|Ls$Sr!$)Or0j=E|ggX*f#nlmQD<ixRG_Uyq*<xh>SnnYw&)k@l$lTmHPS#&-wDbH8Y6(;gg#eT?mfN)yiOfN32InhKjk4+z~3h1-oLkYussRzlzNCPyPm=?R)(y=XnVvj|4q|MVCKUjBL4%gYG0J}{1L_7lU4=MqRcIIBU>Gs6wPDwpv(LHHOWNOp5d4KMywYy`J?C;Kjjy=_0ZCB2=AHEj?oO3UHHSLe=;RmaFu+@;cEU2V3iZn%J@;g&RW+7<dVrA0CRophQ(uN@s(@Gt<nXR1VP7KYKo-ayxZtcz}8lHF0UvBBdZkFDT<i$-I(7a@qP53pdqLW7xd=+M$d6<1UNpF*8@XkB$pg;fSn_v9tkH18RqG6ycJnB4hTm%JPPze)fS!%>v1SLcUXG-jpN#L^KIBS9ndca#oZ;=WwZh58D*?qnok8y5>y-Ok=oSvNY4$garfyYl3xZ~IZx-sA#8{sC9oJ?ohI|O+ing_Pqz`VohKGXJKwaOh}j18>6jmC4J;5>Ff0F^Zdp)b*m#xc-9J$5KMLTisk-DcW!FaXly#{z)V914Cl#)|^=*#GEmHOvu{0<{IiR7nWl5Z$x?KWM9Tb6I=(S#R)JzxR{v30b06vYQCsLg~tqEP$X}kv;)cXI+3gngEfa*%`dMyE{;K?Y{lzUm+QBL4T;_$$k!;h64SfVe}#k7c<#D%*ehiVLy-9iQMk4<Az{~?IgM(vzs;7(iqi@AXUZQ&yt@dfl=-AdoA<8!{;j%3gtjkH+c0zc}v`{b{M#;84l^N15;&=)A&6asT;q~{`&#@?}z-J5&3I5Px9u6qAoReSp&@v&K)s2b<8EKuhy37s`AMetseDj0Oy6SR9&*BO3oNA2xEZnuRXxVqx7Inh&rvdMIN87ucplh>rXz=p!SHJntsEPd9{A^&^~+&Uqg-RVr;hwurX)*%>nlqZPBO81uomsCvkcks0!nBf_1sBq<MqO=C2!?Y%ZBfem&6l_O!?r^R)Cth0{Wa?rxY0ke{SZQTo8$j4KF*NR)qx4sl_)x3yauG1*it!)v@B6!=vUv<-a{CDRm8=zJFCM4RNZt2E5$4a#tmvy012vCv?E;olz<bfm`VfEdD{Pc%`Ac^t(&okY_+S&x7kr`aU$1lznPa&|iGpPvr;y)EwM%)9}*u|aH%um1}Tbamj$Enuf0&@{GwXCE$@+b~NAp^X)DlIk5Wh22@Hi|gK$r~PJRUYk=*>mYjL98dO$8FWvNDj*82huvM34P@1Ya<UdfX0wtWx@HOh)ITJKs08uQLESh;>^2vyC0GcB8EssI^dfx+tai$4(=43hrkw<VAgtEJZ8Rxn`vJ|eR*Yw0vCN2o8AZtizuG^~mUxSInuaIcv*FR{`4$-!+%t4>=^v3(ut|RPUt5G}9Vi)e&Xx7Fd>(6F>o#swl!Az|IY=2nGmP<M5CzuKLGS=&eoq?RVlq6o9z>D}!hwowI_L#Xa7G{i$l*0%9vY%Jp5gJAtdBB94QvV&qJAo6EL8(-fQlpEg%cq;RFTZ*fDcgZT^3=2W6A91GMAJYZQ-K*RxbT(sW<9p-l(5vL)}a>hhC8uz$1``WI0jY#$=qFl-9#)UPMhH7Y!sxTh5~toiM&5Rza(SPMJhgKr=k2e3*w*9N!69%WSL}P_ThB1%*OiVqYWI3gEp^UqnTU;)woa%ZC|xw2VSYmh&qnh{YI7jG)e-nT9w+0&M{($y7y!oR(F;Qz3nD`svx}N$+HvQW}KLy2SMF{~I_FR*Pn@D6VBe7&2<L`5@1Lc#57}3k40Rl2&`XJv($ZRm`p>ynyH$JzTi&MH?4lREP$ZF6F%ycDt&fXE<XGOA$oNu2K;7B=?ZeU?zrc(?qMou7k8%y7^poA_uu&F&-VI1_+?93b(eK=WvIj78PHL;69IgO@cekbWs}dC6uY0*FCMBLdjA9_qsgg6acQ1sqa7nz^mt5-BZ9A_(~7vufNglwt?;Qeru(~JY47@`@Z{Z=9-1UVNQtw#md&!HbGZk*JY%a9s`u?a182;9Et#Doh7e1FB*XQ(uYtn?@IT>jk_`#$}Je%f=5JQ!#(<-ydX<9cT1x9!yJ8X-Ua_0HsHH0mV9zjngl8!nT7Iw&aah!-qG;X?iX)#DMT=`YF|e(>BsuU{-Eq=HFJxN&`2axth%Y-#1FQw8)H3O`*Q60Iu~Ot7o0bIdi5RPy7z!N@4HH)=^N>WIVpp0fBx%W?Z|Go#)1>OfzGOs25^eda5<lc*<GN=p6Z7m`mx6cGSVd?mb<udt($Nx>)6n|F#~dx!9hY9EMRi}a=<({ZynZv={lZyj02gPIk1mbt#cCZDFY{)qYs^~ty(7zzFs)JDtZx=_Vhx}_+Bl-MCTv6F+^E-3!SjGQUTb}x~|+2zFb8fm%n4N2<ZCoylcg~UbbfEY4<K)47z7W+cWmGGq7vw=&!c;{_T&}nKe5e_^Yw^W{f>HMX$xmtGBW9T^rxxt=bh^J1=*bySv92P#)z5`8{x7s9+JtBRY-L@M^41DD>F7zi`fkyfv_(S2ZX*0qs97I@Br1c&Z{T5+8s&f;LI1jN_?DfzO0Vy|%n1gOlZ)`Rr6TZX_*vUcxW$2cc;|i|$zm4*{=8V9&#daBq~baVkRdm4VJhs0OfnOVr$WK;{ak7-olJFDA%*Od8pCf*oB01UrE<5s!wj)1;p6-0MSsxCrhgDi6Wsj%DIuoQ&|~no;2GOU5Ct6qkcq`z~_bhLi$U(10YRxTf27e-#&o+n#Vw2AWEFN$FL{sG2M(1pRA0E(q>T)F053C(lvfttQ6sU<tLdHyTht(`f!I5qUJ-_?X*uDTX>X?{#LyJcf=s5N-Bj`t3RRNu(zDnUAw*QLuMY_5-rJU&c64pT&zi0ugp%A;0a+ih?lf)2HJ}()l8v;5fR;ItebGCX4w~(d2L6d-jwV&PDmVgY$W39wnXm7x~VQEYg#GcT_}7A2sjqjkB>ZD^8Q+G@R_ALNnj^%#N2?RNNio8yxSUoj6T%Y^?rbhUb`k6PHHSihX!!{Ya7IDW?e_(o;?}RdAI~?!fm+bc4omnCFCqd?0{^_i&;g08r8j_F=$$s?VDifHA|-^{m+cn`h5d89_RY38!2;_kvY{E~*b6MR>@b(OP>?xXxb78;u0ECx!;tY|FK3bEgDDy-innFHVSd4PJ#NHDuU2ssQ#%rZXRh*`!&Sea4|DjQ$@3(@OqRGd`<dQmk_BOKjHPlmgcvw=q_1Ou30}xZoZ$DGHENWw`xukMqer&M#NrH&@?3w~q77??7A2SGT<`EBtm2-<|HitL>UlZ1L83D9V5#b|~E)^oLu@eyoKKF}cSB4p*E?{Q^0H6xR!-=j|{mZd2_I3*dt&Qp8?DiKg&Q(i7CBm(h^(YUhC8ICFn|Szao0f97C)7YIwp?(b%3ehvSO9ut9njNY%a4eu7DA$<*p(hY<#v16I9mQjY+@!BvSg}%*OdB|SvsJS$INYgKu>$-;4a|$UNN4IX?udr^!UCwGZ5+k@Cr4zI(A`%R7!G*yyy^#5s)H)k+M1oot62D<8Okitc_MRE84H--z*h0^Zdj4o_-dha{o#5MzD5MRmnp&)?O)TR|H1y4J{=0BaJY-n?mU9&ZKo<x=0A`*+10Ue&<c(P+y+<uv#dWa<z~7f(>PU=(8Qo7Yc`=Em?6?;=hF1#<E;HHf|H@<q8WGwCxylkQMtoTTtYlWa>kIp;bgg78&J+ROJ{%XUYxUyE7~t*4c`dtEPwp%BD~P7s(nddVIKP^N?5z>gu%!Mu_9n@*OZiq|+g;;5SB+M?&i(zBv+;JI?@td<W18QNA$a@-a!ZE}IOea}eZY(?$L`Tw;hXvl8232(u~+$KN43(Xbb3SVm2USYWT_yv{84Gls3r!AmdVYK<XHxO^IKu!9ysoR>+V@|HjI6<b+TgDH@9JSOrq{}{nP*cE4r5e9vopA4I}#Ax~T2SK;SsKVz_n!*S63g?)z&H_t*a;cL=M=Yct_00=rtQOX6?;<yUWr!~)w2B3F2WmX2MT?E|tX<XUX@2s{Lu2K#=}tm}%^0(IV?R7I;ir4EB&D`IwK$4+IwCAqt@bB`i+J>V4!DJ=e~62WEV$H?D-J8^|e1Xp=4=@M|HL-)M<;d||4Rnl`M-m7r2A>mi{7S-Elolro3MeY=Ybt`4tIx1;*_ns5<VRx4$We7Z#NkvX!TG3ajd2i9Ed{1M0a#*)eS82PF)gPzoYH_l2^?zr)TnC%~kK9bP|M#Aow`5qXIA5}v@zD=20wtpxDOK!OkM&k_Q!SQT#cr*2Y^WLxwvxGOG1j^^nI{KOm)^$ABi%eRGdzy$>>1wOoviV$dskbLU-NZ!<49Y$vMb$Ea`xt^;!QmHdizrpoZz?!t!~`Z;ioztmw+$yva$!yAf8m1z`heRrfENB6Nf%RUFP*}t$o_@=ui$PXX;fLA@&W@S8XOX3G?uAlnW($x?I^~bV~Q<i;T?99NxN(Kp6-#a5_go%$0283qo^p<bz`3X5QjGSmu;(Q}DRnbw+&9*t`-4p0C96tkZk;@Y7?FG+YTrL`Tl^JBUtP=)n&5G?fm%P+jb<XxJpv;3ISoYCibx-^+v*;~0k-JkbtgotGvoLyw-TL}y3gGZ49a$S_+qcyCRg9JsFkuJTy%M(ld9@`k9}`X1NSqrFxDi6;OF(X0xM%7wsAjaNN0?%mhE#g<rIL+o8`V+JNw8D}4@HqGjrVg60t+EcOu&i8myp6HVTnf&!lOA|!@7nVp+hqQ+9uBhTzGhQ%`WY~MFuj=Zuvpjw-#U`<5i(8BnJx!12Jo~jg$@iM>hKUFGDgv**{g2;Scf)uNxb;G>SX#G5c#YMGKF#fwEd|NTXQ#?6H)?)i&n!x=qjrb=0*#j$jV_4q$a)_ya{`s@v37Tft+t@y&5S?F=MZk9;%;}h1CYXGrO`O1ISzBu0n?Uk#!q*c@ZGXV=PU|!5{1`EN}zW(3BUSFz8=@*Nr+rAJ9V$gac+Gr_vAQeE#AbnP*&Y?vwZ{apeK*~Cz_w1o}uI3XT4+eY43c{KNxNbwzkXSQ}IYk)iKh#$!^!)7IMO0SnuatzP9-OvPZ`&JeM0CA9eYYG^l)Pu5E6VM9(|M+ci6vd!6^E4?(T0tDD8sTXujz$sHu_dIP9Y9an9ifNi`$djD{C+&y7Ab6)4t_{l6RnEo#{6;T<<x|zKBlZ3>e+AnjOrBn5Es{Z(9!)Ql1!DuL-NA)-4?-Z)%fN}<6%Fy5sm{GW(NtZoZRDJ+kt9f`w%pep}rJa&KCz$S|aWcM>Z5ITYq60y|3$P^wLfM-rrnxlZi16c*eDx~TjhRE{Q`@%mtmgs-kxsw_(T1qr+cejj<Gn1XvWPt)iudYVFtDE2+URzH<78!Zf-X7M@Ft96n&8j2W;UMjqn95eA`Xs!I_$sU$?j@<h$H$E*Y+YXst!lL{!etoUm8Q=%~Q{*XsO!Z(_@$R;h6W?2?4$BQxoRfYM1S*V;#$N<5M;ozS`Hzy+<5M{`|Kah9uc+Ub4DJlvf0Pt#=Im_3yNqrdC9asg^IutvlDYmExOhT63GTEm3}}r`w}|E2sN|b)p`=L7%3%R33P;YPQXn0N0st_?YqPNeAy7Zfo96<lpM4AD2@C4i4NCzp+N^4^NM~=e<Li9QKVWHrL)k%k83WH(NH0caNZ~n6gR@hln^$lGlD8RNp%71MO@}9e?<)RcjpTKxmbt_1k~{!^&Vz+g@@%U`F*wIVx}}<sZbx95(0={|*iNFNoRnhFNQ<Jb=UKItgPV(IhX^&qAAxm6`}W-$y^RVr&F7=MkV|l^=nPkV7H{UBET7Fh@V62ZwWdd@l8ZEpmctRZ-<l_ZeB+9jw#7s~D>^dA2%M%NgO-8Y`U;mkqni@{R2c2-dfksEcr?36`V+i+L8_(40ChqDg|1W;G3rI$UEp(6oof*<0iljxTxvaAT4kM!8a((7oy+9C+A_z5If%mNc1=aWe0qA3Lmf2umNS#2}1VJa!J!CUAIm7aF)lJ>XW|Ds80>(kQTpz1>}O4*+hgC9c9e8pA^rfrS*ChEDWRW^2xtqwdLz9#JGG2R(E)=zZ2deL0kA1m3J-0dMY+1%=UBhHs*Dnad;s`re!$B5`jA^|9esAWKWrzCdi5xFTa3JT7r$O*4-V^6JOT^m7@y2A!!d)#{=7@7oQZD9}e4<tkl1{YR}Joea(;@AUGp)4hnl(=?4TvRb8!N21&|*)eCCoHLOu8ZF8hk~A#1?<mY1ej;O;l#N}tsf~>O`XHZxyXlt>c<eOEg04fPvr`E~o-P?_`s$rEIdG~LYO4YiE7gKl>xnrA=eA9U;8nivSHP>$bLpbBF?0Y~jb!PCsK(DYs(A!*CWO_P)pI2JoQbR50Q%+J3SU6QnOx0~O=Dy(m)I(N9XH=9P_91Is~^?rLHvU?5U)NCT=z&&N1e3P_;>GJM|C|fk(JP&V<1xIO!yG3yoE+gfh8zg58Dook<YlE_lD=M;RSX2wo-K_qTl~PKAVotN$sHe9TfG<?IJ8@d)7k=+5?gFcD?r6ZOf5Fcm20^6%O)sMAo*m=G*MbMJLk<mj&h<?Hj$#o)q|+re~x98M22Ceuc+N)0_&<2Hh8*c2%1Zdr=L*?M&(67Lh;A*2S|+*I+v1IL)y!0*9|B=u5;{CwqY>|F}M><-|%9of^BwyZ5%8%dIa~+3VZlPia*=H(n7wc+c8A1Qmj#5-W5-W$a^dV_9Tr1!9T@`ByPPbClCZz!I7V&qCNv;JRvnEXeUn?9E(JkoV?$wd`*ix}M(V!3Hm+yC1|Zmq%|fI34Vv`wTC#Cac=o_WS6={$cOq?qFjHs!LD$T;7uLEqDbU?ASml5UjyTcoSVSWg9d|Efy!Z4<C}x!bv1H9l;B-Z%BnM1D@tn@jN@wa=!Pgoewv=W01U|LV+V)zM}`2s}45qt9xKRm?F%w?a(Al?ReWo^c}xDZ4iWYqdC^XILUYJh;KKx^KjMa%k%!pi;WpdX&kcrIVbFc*#*J8l=D(i-jw@7*h-s!qowO<T)nm85~HaV+o`t$jAS%~Pw~0&h0JCltUcl7YVY7l1BmNsh^nze{`F8nOX29m3NZT~urla{*-;pcLh-T2n8cc>8dMq6?1H5)AOnhF0<OkItTTH^8alj|XTDwQ(t?-qS{mG@<6f{x?6ikS1Ng==e^RSSO%P^R9`*+<%>)rTi)+{qIz6gzOuc36tf?X=ujtZO3c6P#x*&HKi#QrHcCP~de;`kOQU')


class _CombinedNavigation(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "set_page_config" and isinstance(call.func.value, ast.Name) and call.func.value.id == "st":
                return ast.copy_location(ast.Pass(), node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        # Only replace the two known original navigation radios.
        if isinstance(node.func, ast.Attribute) and node.func.attr == "radio" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and first.value in ("Navigation", "Go to"):
                return ast.copy_location(ast.Name(id="_combined_selected_page", ctx=ast.Load()), node)
        return self.generic_visit(node)


which = 0 if section == "Architecture Intelligence" else 1
filename = "app.py" if which == 0 else "app2.py"
source = zlib.decompress(base64.b85decode(APP_SOURCES[which])).decode("utf-8")
tree = ast.parse(source, filename=str(PROJECT_DIR / filename))
tree = _CombinedNavigation().visit(tree)
ast.fix_missing_locations(tree)
namespace = {"__name__": "__main__", "__file__": str(PROJECT_DIR / filename), "__package__": None, "_combined_selected_page": page}
try:
    exec(compile(tree, str(PROJECT_DIR / filename), "exec"), namespace)
except Exception as exc:
    st.error(f"Unable to display {section} / {page}: {exc}")
    st.exception(exc)
