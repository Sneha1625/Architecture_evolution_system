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
    """Update both original applications' existing session-state contracts."""
    from repository.loader import get_python_files, get_repository_name
    python_files = get_python_files(local_path)
    st.session_state.update({
        "repository_url": url,
        "selected_repo_url": url,
        "evolution_repo_url": url,
        "github_repo_path": str(local_path),
        "repository_local_path": str(local_path),
        "evolution_repo_path": str(local_path),
        "repository_name": get_repository_name(local_path),
        "repository_source": "GitHub",
        "repository_file_paths": python_files,
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
    return len(python_files)


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
            st.sidebar.success(f"Repository loaded: {count} Python files")
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
                if not results:
                    st.warning("No commits were found.")
                    return

                repository_id = results[-1]["repository_id"]
                st.session_state["evolution_repository_id"] = repository_id
                st.session_state["architecture_history_repository"] = repository_id
                st.session_state["github_evolution_results"] = results
                st.session_state["github_evolution_results_url"] = repository_url
                created_count = sum(bool(item["created"]) for item in results)
                st.success(f"{len(results)} commits analyzed; {created_count} new snapshots.")
            except Exception as exc:
                st.error(f"Snapshot generation failed: {exc}")

        if st.session_state.get("github_evolution_results_url") == repository_url:
            results = st.session_state.get("github_evolution_results", [])
            if results:
                st.caption(f"{len(results)} commit snapshots available")


_render_real_github_evolution()

# The original applications are embedded unmodified. AST adjustments below
# remove only their second page configuration and redundant navigation widgets.
APP_SOURCES = (
    (
        'c-rl~ZEqt<njrRFzapKD-X=8^OQouw>64ocuq2jBUcH^DszIM1u#;p`%&8=kmzk^*TPI*{y|*9iwP!s$zQG;V==0iVV-3SNU~$IY8n_?Rf8hEj'
        'IG%{e%!tT%OEOhcJ!k>lC6V#^#1qe3JTI>6Zgr1$y8Zrf|EhQB^v_>j{jz)6bGnxYua2*J2UoArAIE1`y_1vUqu$v;&*^`STAprg9YnG3jJ$<6'
        '48kA{{A7RYY1`>X%XsAPjH0pcBx$@HrOVh09dGW1t0YLa_S#Oje^vbb4E-ICra|gMOW%q8QS{D_S6k29&V?VNCaFJ99gl63%)Lc2jnZW6^R{z5'
        'PyN^%rNKL&Z}l!nmR=Zq>!m?7-}-smIrJC)eC*Fht77_Jw4Kvsm<BtOAQbxNZN3neIP=pu7$sZ(r0twUx4{T)Zxk&TVKBcfIz8P*BS+&U8g&>g'
        '=VLEkIb$D&fYm&GDsDSS-ZGu{gs;c`FlD|*K<oQ6Z=MDt$Da-T@fgjWI1@Y(nE-+BC`ex|hX|sJC<)RiX12Y>jeZr(eCO0dpUnOJEeHKvl2Z@>'
        'k~&j#98rw7j7CS>p3Q<ZLF10$_k|bxxV!wc96V%-CTnkPy<EbVWHxp&JKlRVigVdL!e8~?1#n{i&TR~v^T)!H5<n0H2;BIWQ!m{KCc^Z=Y#9=u'
        'xCq&|K5;r5{Gjf~rx)j!SN%-~+6rciC{CRy$$m>#`LC%zTL4C8e|t%~HHo8{v+&Ys7z`cy`33qj9|>JI-<zSkh?=86vXAF}`aX)^-odByyX@0N'
        '7^UH=eH(j==^z^Z3PCG@7PrwBndugdL)%^=3?d(nBXk?zWuJ$UHy)6WXs09|wa3LZqwN~_bcV|yM9uSW2YBul{%#z5?-gH>ZV0=E2s>r{n{;l3'
        '`QFe={5FH|+yWBsoj)kPY!x47D9U^U=p4-v>1nZj2_hxaU_m~<_0zm_QhbzmW<Fy(CwSExW8y{k>XmbFe)jVC==Ejy>iGO@W2Ai1?e_+U$CpkA'
        'A!Zw}tvwFnxi|9(46_ftVFLd)1_MCT!Jr8nLRT;EKaUXl%mJry2XfJ~zuLh(@#D0y+sZqj?k{^?;5L0>{$EAGoJ^jzB|vp2z6Uovaa(k9ZUEZ_'
        'u$|B_o1aSW?9K7z`Ppgj>}uoVU~X6gEv|ogFhIlG00-Sfm;TyDy>l349sN5*IFkk)u}Q$gPM3XC2S_e^7w7%stMkjRYong{$`_Zp4NFJdg}d;h'
        '5M9CnB4pF$uypbLyA;HR0b<<HbzEvdE^YSN0PaBX#bT9Cqd7)?a+zzm&6nr@4U)I&g%A*A#Fi5gH25>Te6lCRImXPNn652nGY^2#WX8f0#JA#T'
        '^wR+z6(E@)nM&xG@njiO5IKQB*=y!1?65?768D2YmF#BoL*~Tl)APgL$;RiL#;g4;yllKHR`?mrkQg4eGnty-Bsq5c&4BGhVAmu=vg;k-^$xmk'
        'y2mHo7biVLhOXkJzqRGxjr>LG9OKb@aU8|_R=r<(VdB>T)$<Ere%%uuycuP$8^RgiX=hUZV1`7KxC~wRcn}g5VURWEz<Y51`r_pH?5GM*rF}9`'
        's+T&OE$2bH8W1HUk}Nm7#WPS_ycjhW)_QvS`t11X>uQUYbuz6Mw4uQw_Q!#Ir66A|QzVc<yJUnE(S%#-<#GQ{tE{rr-n2lpBH$gGCDN}3qp3H)'
        '^#`N_w@5_iy9ZZQmMQ6BS|~c}DOMiKF!aI^C`SGO+RQPILQ8Iq=qkM$9QIyRTBf{HZI}I`d(^90>P^yi0!-bz1;Kwl32rkki9Se!H1s<zr!j-k'
        'Aq<0CP)(iwDna@hm9}t~01eV{fB5b<zyB})@EiI?=&hn<+Hv0_g_eF4pbHrwuqWuFp%)L3CYz#}{JVt*s;*lT&pCMAzdAp44*Hu@!v59QC%pmI'
        'J8WdobQSvTQIaU7&wRKh#hn6=;paUP-JA&V?*eV%r|8z=K6hi6{{S6N1g4RWyG$oLUohV`LD!uyQ(^5OZ6k^2?KpZbOo;E5`z7AbSND@PNK1|8'
        '!<SFUC&H}ovz#a1#2<KJ7`-1%(^=SoOT)LLcZ}Yn9{vX@h|HoEUXs*-0sUUTkM0QqT=%NCF%lg1UUpxfTn*@`13W6ihkLScH<zffY6xn%yYF1z'
        'wCLB2JU#$qKwq9AIX(ND5xEm=OH_XkBDwloJUdK~aMLp_!U%|-ehtew6utzSnWUV^l-mG=rqVY2a){*;lOFUr(2RfQoFkF!UEse*c(wI_&VPa!'
        '%v*oea>o9|L$c`Lofj^B&~Bwi(MD6wl16r=(6vLIbA1>{U6LR?Bjkp`Hu0-#)a?eHD>rK$=y=$@>H?{7o;dxp?nVFA`IU3gyTm5wvxChM6fKw-'
        'Y^3lXq|qR=6;Z<wXa14ud?l>xkaHHkL)b#Upc*xp9N}MT%0@C4XYK6MnbFClk<<UDC+Ledl}UWmV4mzVvU)yEFmC0GMt|fp;a@&+cGmo%-NA~F'
        'pvO$O>9|{^^&_+r%y9+91*mtVr+^QOfWLGgMGH6t{!BQTW@Gs5wGpw##)JG2(D|WDIwNN0I)Fti>w~G6OcAJ%I_{-uT!4tjSbY3U4~8GP%lX?m'
        ';%6=gf_H$8(cE%m+L{@)!2P;l`i$b7^yQ!yh%)yjL%!^zhWw6o_#4M+9~q=O%<n}53a}3Sw_Zp+r;sXa%yl6g9nK!#Xa@!{fUhx|1;&-P1MX9F'
        'V)zc+Z`q{WvII#Fv;LMKy~T~Zd6N<Kwzf*64bs)3@|=8cVfNxm2y^nU3H(e9PIj2z`H?X><Y{1eFCG5R(n>Z)yU%l`z&vBr#21(mEs>AwqsKqC'
        'DWD+Nm6d)l7g6Cv`RONL3zbqW(INF>G{G9vkdC&~Afb<LC`fQCQPt7zR=*VT_!3960<9$)5WlqY@+ctW%hN;2VtGi$TYGT?HUk}55=9OjO(JcZ'
        '8f?%`MVi=6McT@zVgaTle;OPtjZqmL$yUK%fZ4i;o8nt*`Sh&_CnGH~lb73&m2{W|wY2C)2yW>UDL%zmigy$eMr%v5p`3!%`tJ6scLFL_ExHw_'
        'LW8E?5VRelyI?yZ9KFZ-pdgZ*83>#U{EFt_S2XH4f&`mo9HUzst{m^37lht0L@E)d;ZUFsqbO`BwbwQ}%!Y`*GUEV)ui0;CjTXa6>>R>aaEJgf'
        '>=Qt?#Xc$G7xYX`FJVfx4KcQiwKr6<%&4{#aNEd_NrwjSr~ceYr|j`kBw%m@iP5;@GJ)Z+ixKfST9q(>E|Cy1HE?qi2$(<eUaV4$mq?A%WeX&9'
        'L34lyj7TNvSaMn`oF$gy=nC4y%uT9zcp*?|PknFP4id1m1n5$2*;@+vedI_-h}1js(mN>JICAta87dB<IZ|6v#~UV5xJ+3q0Pcl7kg&NzQ0jNG'
        'xo`{dyrL+zJ}PL;Y>ht<X0w?w8BL5wD4T4HU6$y16s1Z5Km+H(D$6V+pJywhkN<ob#QuOI5S&3S!-WzRWpDp`FP;bUTj7%a@ZDeknRC8Cw`qGD'
        '|9)8<(D8h+Ot-f&Lcy4b^16KQl22gE`De!$+~0^+uyh&yKSqmjrMeBGDQUE5G=+`x1cD)Pa=36{(GeFL=={~cajp>2$ezHmNfVw6;g<z`%{VF}'
        'g6o6;vFu4Xisq>ozycg_fc&P7mi<jWj1gEHbN1I4C+FS6-l6mI_@q}Wb05V%c@&&21iUSHCc4VkH{?V9EWxs(<ufv-sa4;=mJMnfKaZ9?q_YKD'
        'N9ID=K0{P*eC5M4r5CSWqL0dyV(f>0>US{tln9Z_$t1Yzxb4NtRT2$4bNhXamRz0z_Hpgv{oa^{7==;dH-s+==(oKExU`h#fWAQEZRr}kf%)Y('
        'FzL-APhbbpG92S;O3(yD8N-z@2UpSuPVt+2*gr;v&tQe0wVcnWW%9G;!#DfRz5n29<mY1Zl+qCYB?W;M<U9+kluL$6#0(~-IT$c<_asClp)5JD'
        'Jxg33;h<_X$>rQC{JDxtnB7jQ_lO_Ekx)L)jIX^^WCAos;W<`D5KbPFAa`zc$lcAVkHPL#c@sz@^HL1MkVYTkI^hMQYXZBsxDO2pdbGA=AQB%='
        '*iY;6E;#9R&k#Ryu6p3O*hRV~@T8iUQRsW~<$^`{V#9*u+V>`Y2s*@kj3^Q9=|mHTM&*hpIri+KjT3MaXSPhhYaW6XhCXEt<2E;!(ib072f>G*'
        's1>k-F%m>Zc%}|+-pH90B1iB$YS3slkwlAx?{_&1kkGUHE!OUX$AaZBT?_4jz3ppj$t@rrygK+$5R<&2o}!5NJOe}CqqOzx=M(1)9|$=OB%=nm'
        '!Q2Z)?Ihtkfz=5?2M<h4zaq^RuOx_d!F=h9lb_E+Ec1b<PE64xz<)8=m7lJ-2y(%}>pUqmvNUS&IMK9UPA1I+A<RmYWegdhLQB*qbl&^$3>8dP'
        'Lf2{ZUdBb}XG!Ub@V)Uamh&)}zipT);aYM9+*`B?L9&oj#G3tak1o3xuj&+{IsXIfecU)|fj36SEq~?a`XQws!OYLajidH_IUD-%Aes#3(HI|D'
        'r{nDI%TyxwEaD$haSwzNIFbxLMD)yU3dV!%p=j-$lkWX1?C^JXe%N!)FAsZ{n-050j3;A17pD*~2nh1Wt&1h-aJN%(OXqlpw2$w_Vc^GYZkPlC'
        '*k>3%{=8t7a6+Ls8;(6^zK>u(_HSd~Z_F9XdJN<!@fo+SX07l$>3)6w`l=S#A#D-K7M>G=fjf4Rg*O7dl{gV45e15e@dOCf=q&<X8X?Xw&ESUU'
        'CW6}huAMAmaCj!pj0OCT7%{{5$DQYU3@|&-+n*PI1`w`^4d<P`-Cd^N$P4|>(_P`Ud{bz0o^N$PGfDl$03511h;H4ZUmgbV5ur`-at=38_?~|1'
        '=C?T?L+O;I^vTM)f@9Whp^Y%}Rv(k;eN%Yq)&l>7^RuhV^OJr}pfCJ0-A_LG#QEX7|MCCk17+W^LBB4=B8Y+@I$-RL1ICc+a?K%LmwnN?7EMe4'
        ')4yb0^Mo(|ufK8n=xla|s~z}PZ1DZR{(qep5Ub*J=K*mPVw&6(zfO^C^DS7HM3+$@N*PAYij~%NQ_kP?F5evYep$;&A(SLQ?}%_?M8bDL5)8pC'
        'O^Gu8w>B=+yKr87jsLA>M}ElfNjz?5U!$ijXS9d@dxrjdP7rSth0EDIX*_QV-p!+@`(>H6JzS<~BymD^zyHnugA|s;mpy8;2ofvWEEDYE4z^1q'
        'OuP@q=~U*KToy$Qgh<jn_7Poal=iz<ZNI<&wR3@ZZ4fOJ!<HB7W{<P$nRi!SG5qYdq#tVr+i{+j`!p*+^;spTp80pFgD8>#qI1+t(gZ($yGRg#'
        '@W2lT?O-m4cIeL=m~=ENgZ*clg8g|($sx%hBrxaLl!QYNMd)6=+6U)}b6;%sL2Zhb5>}p@?W^Z0m=gDPv4|ri1Sd&j%M!Rx@C9K`$9dXR_=bSU'
        '!Y#T4R`9Qt0QDdYMsJ<%?F^x}w~^qA+IvWU!jYjM=)$Wrs}8lLmbHypPWScI`Dyp+_`vC&9iNiGq<T0HXAds83(r}e$v6uS#)Xe9xcJOM1dBlu'
        'f;~fqteK4B^r4dkRig!w;jg84&V2*nru{H_@5(QwtNZQ@T&Y9Vw=caURegu2RW!IMe}q+_j(R?p7$y=xu&;aYH3^a6?Q;S+_MP4K7lLe<fAP8S'
        '1zi|?wI_aucM0D--D_<rfB;|bG94cz%(xOaMnY^KUoM#tYs()vsKRJ}SUE+j3z1OA60fZSv>(3v-Je^@Y+eS_k3o8~&=76d<a*A*O!teE?m_R>'
        '`N?7L(s_A)>6{$D$qaQH&XM;gIdB%CH}a=Z2nJqEBmLPTT`^8L83R<e+~P4p4MG8du$w$}i-Ci|wrU6)Zd5qPGPV?~w=C#1g(X;u4Y~NhF1Ji+'
        '%VSqNBT4rcua8d-o!;S5ukW0noqX-Q=w1D?*E@6G9QThigJXZwd6h6pus3odK9)#9Cy^+X<ND)U@-izOmii92sEcY-+6b_RZwL5u)W$<M<b4?T'
        '@Hx9jY2(6M*VOtk4jzsiM-0|}wg8~P9eEa)ez#(t%*_zzj#P5JDBR@;#JrAE``sc+lr7QxbY4Sa2`kXQEoDD<yDew63(x&ga!nR?BX5Yr(bZGh'
        'kSyv(J|qEm8%gTYxAxrX22;bR;7l%`v#FV2Wu9OKd#gGD9vp)Hu-|;t?vK1QmC4Q+C>^p{xs<vh->&4}f{m%;hKR!_3Mm)9>p*e|^&W|6@U*=r'
        '-=2KjDWrk{MXTe^5op|&4I$h3e&dItN4eiXj8*p=f49<nmx4yA{u;wdLmr?JOBAS9E5{auj`RXSGsX2GyUAQt?waaGtE|yVaZy5V=!aNziPb1X'
        'AKA!~%5DNBF&7W2z}W2PLh7blmT_V%w=}gan{CLtp`Nc<g>>Xcu5<<BU{`r)j4sBpC+?TSukP^-4_`hRe)Z)r{>s&~J|It>poi}}x`y|~6DGj*'
        '!L{80fr~ZOBRHy}dIULjR1aQv{5bhpDmOe5KbpI=lOLD54fgbaAY3<%7S70rEU}s)Cx{ywXlfFC3-6PaDQdA|{HKxjYBo>cW3$e^=jxkb!9Q3Y'
        '^11qowQPa$7>onw|LN7vH73C=!S$EH?K1Y|Fakebh3ShI7SyLuTrGK<8yg^^#kQA=G5DH@Px2gw;}k~s%C!)j+t(9#n$9T84eXDdel$sOwqDk@'
        'tziM~oy^L`xA5kpX%s^$6z!dTP}usX(fiQ9MO0Sh%Z)FaAKXsU&M$U%HJ6c4B<zZvXzt@}FgM(#Vdwd-<}zx(jkVvVoiBD<Rp`;3cNZik@_|5j'
        '8wXkd!q2yU9AQdgXb0n^!RRe!Yl*2fHhXAp7X0iyeX18Tbl=}p0@&&&fZc3D<V&WtHpx2;Y4KtOOc70!PibfU)LT~XS;N(Xor)tf{3)Kpa^;$}'
        '<~>or6x+OC;sdILwOHcNiJ335r!n?f%pgK?fJ1xIHfEkFnVcW)2AHI^V4DxYW(u5{J_&t)As>%@;<?6u7<qIBS1ZX=Uj?JA&3i6mq1*Ve^YF6!'
        'OYBs4e85=a>v9|VuR3yvDT(ut!Z0g0$kzEVflbl1y+O!qky0C^!P;AXno>ozWTr!%J-1|MR5iBtUAI_}%$8|1cv>&OXxKCxG!2GKjRCVM8Axrg'
        ')EFw80_K=hbh$xNZirMHAT^4k+~6pXcC~@A&Wp)E1Z{dTWky7q@latjR2mCyjf8sRpw=j;HwJ2rfR@HTt<g_!?9&_hRK~rg?mC%`cxB_AYzV!v'
        '&dx|@G|rifa!mmR%{N?Te3Kj9jK(&dk<HS$W-zMBjA=4zp*5cAjb>V7nbJsRFpjB>V#4a1k3-x9qt~X?O>68@7`b%DEtOI0Mg|On@k(X1(iy8Z'
        'FjA?FQ%0kdV2simp;X2vqtQugY?2$9<i;hrQK@W95-?h4JTlopOtufR%|lqs>SI|9pWs7n-6&Z#?5r7ruN+#IE6MG+p)z;cySh9+s3%6p<eoZu'
        'T5^%*U84_Vc}2mVz)49>F8F1%S03~YX^tp?JXK_}obf00bZcF&8qS*rR8fAZTWV(-O=Dq)&&oTzic&9>!%Gq_$_6QF14_+FcC5ln)p@bDY6vOZ'
        'Ywt=!3ZL%s0feGnUDB!T_34u8s#jaJDyyKbmQ_`)nyOb(HR`ECH5Ii<xk{=~M_EAYgw(PMT2?>hs%IgR<<eJ^jhB-tmCYh-m_2?`bCYOoQjLw('
        '*7E3M1~=4Nno>hkYiD{rrmQ%LUDf&v(OsaCLUozAd685o=<29-6c)hxV;A+3vQDDaM^w6qg&v~UAk^A}Qga|$!xt*62tm(1RyyGGS*fILiKMNP'
        'vSkwXjWCHys+LLARGMB_a+XWYT8WvFmerE7OiI>D$V%yW*x3{0+OYIVT>6BUhM5ypNx?dyQzvlhg-vGS)gNNwW*&GgmuxwyRxi;u*Ow2gia1J{'
        'kR@)4p(x+yhC)3Momp`YO-OK|A2*Jgtc)NNtiEDmEZ~iY{;84ej^N?cIV3YMOGUZ>op!(dZ1UjNn8+zF#ZqTBL9XaZj=M!hcP1xhQA;CB3C@d+'
        '&izB)7KzMrsQWzfb!p;ZLJFXAs?@x=ge2=LnqlfClC<BYDez(8DvN{ha>mAVHswi6vmx3=Cn0jA%FM9C3UlHUSbw$wKElDkJflJ}&(@I*v{pH+'
        'jA25Q9hZX2562*%UF#~BsLG^Bt63<^47jueJp0kRAfk=gPvK1&A!?2pH`*k7s`F5v2_eF0=jQMpfY~)}d!tLNub)dXpQuGtOrQ%(qlq198F_i>'
        'rlgV66OXBYG%PZ~9gyx$`aV)sp(ojv$;C+HC47z4Xi}#!Y3C`6VNC--vJwd^*3c|k4z(?ZIVYJgg*$LQ=AvZDK6@`23Rl!4!S_ng9gD3rBu}8U'
        'r{)PqQc6JH-Q^eVwh+9V6`p8R3sqvGq7I90)!A4K$Sjs!Ql&^PV<x}<TYuGHKTw_(S3E&>TuchgqNV(J<dsDTD22YXDO>YGw@plavJx8>3z60y'
        'kuQW+QK+yGSz!u`HJNHrD3*sC>Xt-&aHL1JZZQ(&Ic5X$ShLAtu3axhb;61z)^p73uGZ%4RSQ=lfIfS_w318qMXBye_C;x-<(Gp(^1$5YUQ(<|'
        ';1iq=0asp&@GOB^liZ!0j-ns>p|r4JEejjgv@lL86M&|t+S~%g!cZ*m1i>#~rgR0vT30Z%Tmeyu3Q5x&Ln3Sjxcj9nhow{9;jm9;bwKNwMeiyO'
        '?C}E+r2{YLMC7VE^q-iACZOOUC?8oo$Q=>6v@oeYgIAit1e|r|_!H9{4^-G52gxGzR&rrmRvT4T3p=Y}>Ke3p_Fbu*&ZqRKln+o;0W!WRQMFKR'
        'bYOQQ7`Mt*pC>fGAhC(w<9$=>cT-lO6J{22%CA?DQ!<c5i<J(N>zeXmL{$`iN`*YBVk;k^to7bMh<WkxW0%A_L;ISHGsXOwZoiJf@J$I~z>Fyz'
        '&1S*_d~!l><~W<z`@gs`KF><6mUMrTwA(4X<_@HGi0lPis?uvzJLO>clirO{e^Z%+N6*obe2)J6x#C!!mm#8hiZ=m8WrkT7F1qpR0L|y+twY(7'
        'DqEfi?crxvIpNP`?hg`kR0&vWK*{Y{D(I-(7NE{!Ms|1(F!HcvNPM5n3t|`Dfcnzk%kPgkBNL?Hxm$R1E|(b;O8P&XH-Z1&k+Li25Ge>jNP|*@'
        ';zGYlA_=7UJ<};m4=?rPCC4e`dWT$s@>)}q<Dd#8V6aS=Z25>|<n=p>Orqudqj3=75{qvM{?Co(kHeSbCufo$t22q{^8d%<NW%HQ|Kvwfs~<`1'
        '%}Vv06p7=W^4wp{2iM%Mnl_e+rM#&x9FJ`vhTCx8tu)`2!*95+A1@4tU%et6hu?-OET^;~b#W?b1dVPuo4^*$ovw7R73V99bL75zym&`LtfO6)'
        'JK4jkRjxF<JZU_bw5iMtdD09y2Mu}B3^~%+AP!86q(}vhZgF06mUCi5pLQlL?t8C_#Mk6lF=Zkm41))zI=Fttw_K@Pnsc+6MGW!BoOMkS{;(b('
        'bm^IRK<H96898k!vIID1iLU9}S4iK)bLcX`vjV+g3s#Ajl$_m!AbT40u+On{V|dhlH1E@vKnyzMpO(QZRd7o!!xo=s?w5KDDBz87g=rhl)Vof}'
        'EtPtucFI1f2%H+HRJ{kP)Mxea{8FFp?#kEw!97#|aIUF^%PB^wnLl4bCVJjrgO{U7PEL|_C+z95lM^&69Y2d&yH6!wtPrh-bnNBuJTjlSM#EZj'
        '!~i&S*o+uF+N;TypH8E3$EC&|T~man%H`!!fiZPs#?ylb*W4DWJ8M#1%YF=bjC7ig?nj?#@}{K+%e`@Y0u^`PqA79fT*frviK9$XCb4RdV-M;G'
        'sB<E*KM#go5o0tu8^Va!TKsdH#ak@|3a-+8KKTyKy>OYVea8)EGk+YA8(>(91_=~=c#|9boB!nWp&}=|6+vOskMc6JHD^BFi}Lx8`Jz0tyePFJ'
        'ueA_)^JoDfQ3x-*QMiZyuX^Q0t;&yFr_p#B`jw(W&^$kyxDW)5^&&&|*vJs6%LNjvfBU~Wq<qq6Wuf9TTt><FOSO}jOeQYq{2nnpLK!^xx9z;b'
        'MmGGv895yoDwrn=GyvNhjU2>TwN|huwVkh{r8Dy84idW}=i4ZnVWSMXtfYn$qTsiPJha{VVqT7puU@@=QES8txJBLu>2x_9F!iP*TK}+-7xc#U'
        'uE`<M=F2!NUf!SyLM$jw-e8``Xg~IB@rPhh$*O6qnzx}5MJ=eZ3=?v=TdX7hsGT76TQKqN?U;PxK5?7EOK(1C8(pRZUS=75Yoo!-Pp#}a^4|rM'
        '^Uib8;JiR2Ct-WElSLS?o+?i`SDonn92<V!*VJt$Uvh&pj^lCBt?W2O8Y{p+mjDJ4rI`x?YcX#az4znnm5|w2HX|PKdS~xui$4^4Tn!;C0ylno'
        'BfkCRT|||hk02Swpx<Ke=|$8gI?RB4$Q(V5&A38(P%n<7ST=wQZ{wq>KSnpBd*~VibBc~Ug!%PR51LW5oa09Va{`7zR<*qiFSr9TfF$LnyR+kk'
        'p{uulXx1;RY*+BHEbwYhq?7zW7}3DRXO6za|FT~Y=%8=NFYH$chtTK6z00l}+lE~nYRvvgn`Q2NKzd>yj2k?t1acDw=qp@lxjM0-;|gz2<Ws|8'
        '(L-XN$L`2BI(S9p2dT^l5<A1tXQiegeu_-nh9IDMDyz6az5(jNwY=U{RB{*xlL>xu$L-qiXG0Y&lkcMR9dWuq&>T%wX=j@1nlUhG+rx*kuNFo*'
        'aJ9YhSg%tvgKCN>XqPm6j3o^#ElH9xH8(D#{tT0Aa?ok)`{;ijuG`+wKpXnCNrVETXu~iXy7g@l4{p0bLmZvqe$X43z0KV7on7phDodM*p*8jI'
        'lBq`=9r=EfWf%@@I*T1=ev){%zNDM(LbYi(X_Jz8!hZ=;0e-D%G~s?L&YPb{J0up;!L5l>ylhKbCcA*^EmNEjK?O4MeVgO*j0li3R&iXgf2v0%'
        '|A3npv?B?Q(|7{ED10M7{d(uq+0Lh9=hIjFpPpK53?tuwqM~FaAXssTS{i}-Rx$#0c~=hd(B$|vMf+O3@EGSi=j!;h=bU!YCuhCdH3r7JxWuzF'
        'QpNK-DbFtRZK;DDVbfFJ8@IU|YZR1d_uT({tF(gzVX<K!yyv`h_e%LAzpk`<r&vpQnM_LwhTzYEz|l=02A}w>&gNwclS)y{AnOQHQ5@U`bK>z0'
        'l!R3VRHq~Bo{Qe_Qm@Em08WF&m_afaQ}JHlC*?t9k$H06Lc+l`c%)lCJ_iVVNtR(IX%=oA*q{UgTk!=D1PotREG=Ia&_LU0*Q2+kRFf>CNG{D{'
        'g=q6UXS0B@>_-)@A4ya|my4xJW*p%(%Hl2jV29^u;m=jY6X@WI0?DdJbbmgIpdvuWU8a+rFI25SVN5zM+9Q-gkd;qxyu_I(#HBotcG5=j@VFt%'
        '!H<MA)WA!yV4f(r6m<wvLV);}s6o+`ss#+zDP$&&>1pcaL<tu0&@RJ;vE-TI$Vzyn^%dAsSf_p6a^Y)LR~oy#Z>U-+>HZ+A;=tcwZACQF)~*Ut'
        'MgX(}=FLoF8pLiwF+?Y8Y1A-}Rjn-zELvOgEw##i9Efm+D^ns7fy7GoU?7SLT5SZLTp_DE86n9VBpH#D&-#~Pi7+JR$ri~hfitY}QJ3(*Sy|km'
        'yqy(O2dC$Uy^}%rP51bu`{Ja>GC?mu+RNo~4&pzy{R!b3+=6g^BDCz$TcqGX6z5zYiz#E<KgmQj$wWU%Ge1c)KS?tmlQgrIjF88)cce_fUUp!v'
        'c!%Q*YL%bQcPB0%5Z$l9D<*sn0J@u%GeP_T(NO2!FUR=&B)I&@1s7?W2uQMk%lxTQJ06iJ&cgtEE;O1pDIzG&9*LP~WI2P%$?D{R@7KHw3l{`#'
        'Ij$;jTo}5P{-#(Dvq$;{EX{$WNPQ+tdzP^2&g6v&j^J4WJDu>e$exsCd1<(9vvI%L#8~PaPV$6UMJ@_q`TFEmnrWm-t(4O+S^P`*Xx^=UDY*|L'
        'n=z}@f?ryBd0BXpba|Vn0E;$S90gAiMkNK`K!^1@VMvwnPnnmiDFcsjdeW@g^wR8K!t~?{f)kl)%haDhz97k${G-QF9nT$S-8aWa-K*pCvyI<1'
        'F1km(J}7}?l@P`8@0@e$1eHBvffL&Q=ky8U9DuKG@x@>Mz0>VqIenU;ll|&{|JV7)Ug&fYw_7Da!ZaWOBb<P83fe5w<afV!a;LwQY>dDD?}P#J'
        '+&5W^|MTx0;(zG8fP@BKOq>Vv8Gh}YM7O~Rm*`k7LZptc-~M}k_{$)9%Yx-U@LwPL!<6~@@BWeh`jzj6>69J*Z=JqB^N{p5a(c6&KL%}x+uomH'
        'g`B)}ILGtFvKasS-~2s4{1uV`ol~S82RJ@$>!y~swTp|B;{%Ls&eieN$>!NDkd}o*i5eO_fGDCc3~te}`%ZraRp#8SChp5+BynjP{1!w_F1;}L'
        'mXJ0d%D;N4k1j0@L6Ue!VoFc1_09;Qi?c+tKFvOxL*9QE01ARVrJf|-$A`Ta-OG((ndMbU(DH^}<|HOfmG#+|<KUe$3Xz=HacTRVFuIN0uZ&0V'
        '<rCERtIrsh;d$as`~lJvqW6PoIt$AV!?NTtZufWx%^#ri94n5-%kH=__m{h~v%|GofCUV@CCA=4V7+M1ym!GZapErafN39-d;}4hyAJ-ajel=w'
        'O9U&@@lf*;EJaqlOr)<0PdFwS07M`RaI|C)2I;DUgyt|r60bjIx<mOX$<&pgCvOGm)h^=bSKt+V5iERg)3E5~7Fy-@c0s|mw+nXr{a^g`7Sjm0'
        'NJigv%{XdI)mcq@hI?SW#&&4RM>NfkVCp$!PjmhR^94=Y9wi?;M=|gqg#6uO)LaBtEu`h({PYyj>Wl7W|M=`^V+td_+EQ~zW|l;sAR;gzL^Lxe'
        '2NQA^X%?L8EhX+NS)3JzyD9AJj6Xmac?iOs=UBt|Xv0`?@YeWmm@P6o32_`w`~eah@SM~#Tgx#5A#$EN-~ak|&iR|(<(uQ)FE>8R>|DSdgFlUe'
        'ae$p&$j?QXgEW|z;}RlWcpsx?a-wiGMcPq<`8uKa-y-Dk3YNgIUf{$dqzz%#oG@Og7z=j5rVB3}EEhqtT*j~+%;UiomMT8L=i9QIr>B7j5n9#x'
        '5a=KxvaUX8gQI@kWg0<U^br`<G7B8u6;Og05-^U-@f*>^@fZc3f`vj%Ew{9sF%u&Lvv98wf;7{DdFRf|_Y#;Bpu|HFqJ|J#@ngiX5jEtz?H6$b'
        '!!VGJVxjxk9|Z}H8Icn^J;*a|Am=+`JQDu@b3Q8RIh%bBI`GNR%Jb%PKSdb-{eSzvxr+Lcik`sg@bPYMt9nZF>AArCe#Rf&_kZzQ9wYEWpFFW1'
        'K*4%zduwj(lwe8Ktz}A8i$&7WY83jk!~<wls$D&^-qo`;cSX2()lD6vQ%Zx$O2Bt?B@iW=CCdFgx8Be5wGq%uqRRVuxx^@zUFDtIOia1#9+gH)'
        'z`Gt=#tq{g#_atyW{)hFCuughq;39t%0?4%hcT0;jFn|abg&Ejgz1R+H*wm4Yj?47nFvX51ZMNWY#FA(0*#702}NA71f4~HWe=@ndbgB2w^%EG'
        'o}7Zfhex@bi~w%FUIEyf!UB{1+$&65`*_Q3xe?06!_p>5KLI7!ZwMBzhpkfl4z$Nv?uw0V$+CwTw#dj}g@`5Wa;?$A2r*AQ96ws|@NO|46YRI?'
        'P|VV(iJTkDrN~K8)m>*;eAfJ+uPFjC_h_x5A(lz8bzY7o_fVts%5Ylw*n;j2KfG{tmgtfuiTHZ?{onj62M4zEeVY#~0ca#m2gJaYJXxta_blE7'
        'PCc6qPYH@LX(t=6qTCL%EkOk4H;0JhpF8(3-1TR0;Gf+{0{1hA6#msyo|~Q0Ms%JKi!cL`m8FyL;WA-kgDKOHDq-8(M54owT#)pDks#Y^GX+L8'
        '#$q+e6_J}5`lD#!SJd}^%eKFO<lzZ;>PZaCntl>1v!=D#RG@BN*bQuZfN{Zjf{n|XE=NJ?^xh%K7x=s7&^sPhD-f60bok}eOLx%q?FWd1dUW(h'
        'F<oGtcMt2l{qxtC2R-ND{IFNE+ABO|<Pib?d>O<tRbH(Z3nNJ~>@#))%RJ1vI!iAu)mq8@#ihFyX_+x)0<&d{Nu=n{morGI%#a{vNu@wecpfyG'
        'IZbR{B$>ri9!(Jcj!0mnbd1JH_!@8LM)h1L@dKe#>3N}18pC{%PJT_KE<tKp4n=HGJ=14Wcj--E_I?_A^V=mt)Q(H!Pq*e|<@kC%!`BNboHbvo'
        '(nH_|7YoK3CXl}lafH=8_3oT2a3(W8FEH<o2uou>L3{vHEXTjY!vTi};|YJeuuVw3zpOQoy}W+t<8dgS!C%8jcr0-H_;ZZRf|Xy9MT_P&$Y)g6'
        'FrasR=B0zlaz5&W-fTGboM2y8S<C9iiMQ^?P*A~|QrJ=q^)xt+(|nz+t~9;Y`IVMBmyjdK47>C!_z5!vkSR!tlDEakty1ngb&XapNe9$3m2_5B'
        '{mZY0!l^;CDt4Zh?3*^a)aII{QWD3Gg6rq1^I$1gz&_5+)6QO{tg8h*Riq8I^DNYh@#JW<euU*=)k8{#Q)&Q8A%bEtC;KZx0&3za&xz1>b@>{i'
        '8@eY>_pE#Jb^o|uGnY~Llx)Cj6eHR{Wpv5&g~E?ui7p;Vi?kpr&SwcZo|rSH(>IW~O<qReaimyOVXg<6^46dGNZ%;tKgRrve2$r&@_B<wr7F&5'
        '#waZ+5hNv?fh5voYYHvr3U46JbmuPO0BMa`!mOs&3Ar4@!l~&*7^W+i3&XOPKO?b|JN_06f=B{#oCD4`TuuLEyg~8&Naa!m9n>w$6kcExVo+7A'
        'uovuYqY8+VMRD)-!3(f&#Xz#KN13-hUbZh}VEUtmF5awRncz=ZK&EL4W0jpxl-;xQ%}r0NzAHg=)+$GjLlwlNv;)e`a<E6aSx%joh5`^41A}OC'
        '(!gTMF&m{JVI_3Xo2n^*6f#YTV&O@&%W!$mEZNVEdLn}iD!aD2HVrH~<7!a4r0n}!1}v6T5K}Knf2Gt@8P32gW3ImxQ~Zz~3ny;=1}_a5s#k{m'
        'oLDB<TrN0Bwr;l<mDlkGLZos`dol7da||hawg{$-Xae$NAwIIRV&eu#oB4x=joXVtX8Ym0fBWlvU5XU`)ulFwGa5oBQ#KsQP8ciUt^66h@F3yr'
        '?l7B{jbtVF*zhUE8jlPM6W&4?Drgx5E=D(5g(8|A*_gnkJTNi0oM7F>wF+Fdw8<bj#z(rnG$2i4ondMM%OmTU*HLMNx4omT`O#HxnSvjj?@RV7'
        'YXQL06Y?YMM|_*M+mY~iU2QL7s@i%s!aZ5*cOhBcC(cfVA4&Ja?p60ix8HLhmDq9rs&{tK+jN#nT4fH1VB9LIW(Q*>s4=*`cm6;b3JUhop_dp0'
        'j;u$g9As%&DGr7g{<iK+5VuqM#CiaPFdhC+jgVMHmDXu6tOoJh|I9O=1$~wtLze9f_KvF=qfxBCbI+l`LrdE+KeKxVQy!YG?KWj1<9Mi5fz5i1'
        'Gz{HG*o=e@J9uOe#Ga;^Fq*CF!L4|RezrUHlC!aGN8Xss^n3k2L|OH(&M%QXTswvF@4$<9ev7$2@zs~ZM;UdQ15kaNTt>3cRPk`#N){|!T@Vy%'
        'JGq0Xt1{B3P+ld9tK=hE*o4W5s0NdsU|K+F9jOemF0yN+@fX6ut1t1RfL5F9iv^V}LYQbUb{b>+fH(yym#2xaFB+B<Q;vgV5qc{*J6#I_GRG%r'
        '&GU_(s$?d7`N<hlM=8j$dxg|XtQI-%5o^e4xkC>H@(!;EVfR!+EaYBVdCm7xv<%01IYZy>q&7Bm*r!R6YkV4x;y;qX<mcF6a@f1*ogE^X^y~T_'
        '-9Gm9@fICLkoX4n9L0$1JPOjt9WJ&5EYZ;t(0n!w;I=wGpj(l!YdOcYRtj?tgd6Z-QNbKZlHloyuVQ<P39TyPgn~Fpaiu&6uEOOoob7E=?`0=M'
        'bA}vo+}<uML|Kg&93Vto9vt*%FvpgSr5CcV%WUbGfQiw{_W@6wq%IZ*2&F-4ef*%^k&<>nqvuY~4_}}3oRi+0-pQteZ>c@NTpBXO`q9$716<i6'
        'qYqQh8%;Uj21#K7L}V5bHaK>2iY$?K@zXKHFF=>Ep9Hsac(X;aQwZ59oTDIpwHy{m1ScSSA1>aKEMJE?M+2RcqQJJ~c1O;pdPH8e{Squ`Jg>ki'
        'W#&lPOTf{9z%RE&lB);_*z*Zgw!Z>A2B({B5=liVM7Va>;ok_@bm1I98T%>rNis__3c+Dx<>la{*FDSb+R<hA;#KYX3&L8GqAEe>i=^4CK&=c='
        '8R+HGSK|BQ&U1w`(c8|RSdf-^i6b5sNoP-12~MU>OA4uT->oF>3%SZuE~uWNl)SDwgM1A`?z~JnKu}d@6pXW}4UL=X*Wz+^J@&_{COd9uRhPYh'
        'xVCIM{21!8>z-82b=mO*`r7O|e8H8QNfBsm+3>rLu4ekGqpOo{u904pzgF%sFPvV*Ezev@T>=+U6J36fNELL=ci{e~`5G@sa}A*pcljt4S6se3'
        'bnFySp`ijz$%ZoJ_^zpLw8|Q-6bOlPgrFJu^{MrD_*$W>>rL`_B8^oCm$ie@n{ALkE17umgEHC+@G2?~jSty4_Qd^i_|-k0;o-|C!>_&^#$V~I'
        'lCWc>9>NR{rnamYxUaQ!-sdMd_HSd~Cor`)au(&^t%wLgMHLYtIH)5c@Cu6*`kyJhY_VJhHRAIlR=2^DDPpi4H;oofss4M3j1=SIKaB)OvqZ8B'
        '1HnszZ~e|QO%YfNqFE5mJzY{=%a5gb_HW6#zYK1bZ^U49@2F`+!G~H}I-+ZHW4YKiDG#p|=y1lcj=EwmIa$5aTCP-RRJ4`K(V;ZhoxAVssw73y'
        '0@B%nE1lzNF<DU&81(kgzeVd(m7>GQ?FYBhw4<y)j**|-(@_{Dexkwu+hA_M-60ZuHOR01Hr9TdcD~rH<lTSg-35v1x*`zX#(@@q@bj%7NBHI%'
        '+QE2fFnWs_M51f0SoG@0wrIKiU0zgLxYqJH^u?wPQ;#6!3nY9|l%M9?mWncSx3gT7TBbm%>QtK+x@R-FqbO)?SO{0++O&{o`h}><R0{$LTP~X}'
        'sJY*Mme;SAtfK4%RgYDV#s~LKdIwj|`B~3-d3@4)Ov4^cnByE%3+HiR1BE;$7Ey`Bd<s@O!DtGlyQ6uy!l{=6U=edPDr3?!T2Sk^-)W;e_z)x-'
        '35PA}R`HM?JC)nA%E~4Qb|lqICC}C}*Li3x+!dVcg)#JT8*!Ccr<JD4-~A7{!M~q{hrTTD(AGF9cLh4iz)TF5W;<o+h%AY_+NqKd1De<8&z*Y('
        '#JNeE53c3YHQAuOv6L>ioCiZh@9YvKEt39}WWtbKw^C>R)yBu~IK<Kl_J9=Z?Rd@h&NXURaC`HpqC3z*h3U28_;RPx3g*`WUo~Qh&IoHT#M&5R'
        'O%^<bG0A9{)fs0oGU!dSm8_oCET0vupOzL-4Gb$-LM^SKrUSDzXqYXdX6vY(g|xE5ud<YCGzL41smc1KL3W+>)WU*lWkoGpQVFTo+EMLosn+&X'
        'dz)&pb6jBD(Vs56pKD_XkJA2XX@@Or9%yZD%iJzwfQGisb!dRS-Inm{m>4tHp32USTi9}mY1U}UB^|C1K&d$wAN+$&r-Nud_lba^GwbH2U5qLg'
        'hFznvyb?Xs8F|fy-b%(^TZ8W!M&D|NUwh-PwE;Lc0`GmHzf6{V!NwSD;111duCzABVG9GXt&!NqP%JkV>o;LzG`2Au+ZvBERqyvW<uz6uUS`Vq'
        'pFj>cP|YpuIrjGBN;YJT9ogQN%-EBE{`s!qPTAO$t?kNY+p^idY_>7$?aYR2W@B%zV!o|n!mVb;HEd+{$FLD~XouN0t+h{Avr%i7vavpY+Pk_u'
        'KIlJ+GGE1zZedKvq$(qaiSxucAa)iFSx{MfD#6%bX2;9Q$@PI3hLu*Nw6p70^vt{>y|rCtamR)<mA(BjagcG|zJdtlM?prT%@IS5njQap#AK-n'
        'E<f3_gRLce7$a&7PSTHN@ewAn(qHb)@<`uQCzk`Ws%EYPL1A@?b3V5mIxEL#9{Q3gZfH4pPFN6Kp>h^nWrKY6P*tZ2CgLgSGq-?zJc*6Td4w_b'
        'i>}6aa&as`;x#E>rEk1mju@kjJ+rgt7WMqq3TmEcy^|Fyvx(-ROVb3NGA>uEBBzitrbqoEQpEQ7&ANhPej&+rLK%L&(J`tDi5rB+sD`wUkNKxd'
        'D0-OUm!quy%nVl!CfQAxurfA6rOigUB))?S96-?;AE%01=J{P=h~nnaaJAS&9~bew>C~HNS@Tf8A>fE}a&oGSN;#?$Eg(b*6fd+#<`*vATdl_j'
        's<Fk9CHGAJaLW~HmaL~}$vuGaZ7I`Z+hTErJQ8KH3m<hMds(HmU^+ONlaNvQuAKys0c=1THIACn5prP`{ii4aq!D7>16dhr9!}CXVTJVRYODY('
        'Jmq7`<wvcb29g#jxJ40>9r(Fo^BA(ih>(q#fLvawTAtxXof^9Uv6ER#-@!g)V-w3LPEaApW84dZ;_-m#t;xt&tVbb(<aTO_Ov9hAy#Enr;FS$>'
        'JV)3C#b#9l1oMGujPqrB8|lV~mZ@%#2RYc=NhGSy;4wj+FYd~d-CgrA5z<q}5Z##gf^Z_BlU$l&R>hBLCn+f<qxynyzhHw5U!1=_JM3N__v&Wi'
        '(jvwiaBwu9n5|40-00Pm*T8~eQ47qt(XEN*x46n(h<Pf*Xc(s^k`tHkWJrXtoCDj)bLL8YnxLxX>$Bslucg_t<Z_^!4?ZBQF^b!ZRXNbz#4eAj'
        'MhQwH1bJ7YBRek_T{s}f0woDYwkKhBRfb+l*#Jy3)JSUeWhy1g#V&;i@kEKCEIDW-bw2kdnPcsYHKe;f?`AazA0npk;>q3y_O{a;W*SwPY{UGX'
        '>=q|5NJdd?dRKPOo^;*1thP30y#DeQ$(uk_^p3lgHjQrKAR`hMPd0V#8P}{eFVn?J^&<93@<&${ez}?UPLbVgzOh-2{zXr3yjRGN3QUmFsj7K}'
        '8k*46jC}-S?X$Qt(70I;BEvB!*`}y>wGJ2W6%T#QHe~VD8zO1yMCwy+z9GfBaCXF&!M%aX5%(<U9^BSC-X1d_IAl^~v9ya}mDe|Gt;fnrO`rg#'
        '>U)4!b<YmD=|sBQmgBa6g~WfegTc&OH0(^oY231ENFi-*+^omrs4j!xX_h=8^=XC`gEg=wE#aSFE#c(+==h*}f`r-E7bkTTXBYC|{MtE*ZlTb$'
        'lU3c-7xqRSx?BO<Qg?fc9u*x)3_&{eQphuc6E`7!U^IoQM@|}{J3RGctiT5;QqK}xO^`1O4rymVWkl;h`Wq5&g(|ze(F;%I#f3v1$oB7oB!JAx'
        '*cLcO$`M)_Ul=<?YKf^%Ms`fqR1N~U!3-4BwbTvzyhKW-W%=Bg43MB$G<baiCLrCaXb>k*EYf3>3gx!b@?FrBiNq*~a}62P4qUz@;5L(krNp%i'
        'ODBk$fjd)z6ArIr+n}3<X3WN^DFH_Mrj3^PO+JQOq5hnzzA~Xb1?2XfZ|=!)J$z%T+@w&|@LsZ@lhU;<(`A*urV<}5iktw34?;5aAUg<+BNpCp'
        'CAFYth3Nn%T}-lAopBu+1WDwW3_SCg@U#0NRVG|zyVl)e>i*&PN^vW}Nzg5X>AZtxh1WM#)wMZEOh`tq<GmCTbOjT1edehXiUh6tqp9U{E?X=m'
        '-_G^^-tLXLMunXKOvs(<8XIkI<1#DwG;yhwf%jR<`Rw)l?Ho<=S@VG@G^_gg{x5#F#yrE)JjOwGa`Nh61Ia!=Y|i-cmuUFi=EJ8J>qo<4;b@#o'
        'N2P%WM0^4oJ5R~TP8!Vo#A0~UF*J>5t|(<tMJl(mxJ}Aj-R{x8UQzw&Zuw>Y^0@z}bqnkN-YFG%-Y8|IWW04USLSAY#&(Zo?3uT6hCce#7vyos'
        '{kw>mw2#ET&lIpDWt{H7$`5hOtlUKugRH`xQX;P+6H`(RXI4dWj}gEIi`WOpSo?<pmGG^6!j}l$g5)fYZ6z@)=PM(HR8+RF<aa<EEhN}mPc1*{'
        '$T7g@fr)9NuMyLd7No!^(a9Xs$`+Bk0Ttak&&24_vJei(pe`(?W%#(LHvv1@Ar2$X-A>FI8zsff5V!tZ#;vnNU^(+pl;Z`+>T-Fxuh0JU?EIH!'
        'cB$DABT6t`b5vHB68{ysFQ&MzqBn*fGeChDgcm+}y1T3Fd`**i-PlH<Qy3x|{p$GWmAf`KqfoJbH{#|#?HwM!KGn>wO%uA-{E3Eh8*5%voK2@F'
        'lXE-BS;oG@2}9Y(R1W$V%9B5sF5@}h89p)gd$GLTnFM#VL{h?yFkIfEuUJ9sQInEma_!laU{g9Qez0WZPoI{>ro-Ngy35S}_CN59=g=Rfn}|))'
        '@har`X8Vp&-^`hjE8x3`BgC&~xghn{XPgjy-lcEq#b}L?9A@SP*eC_bD*Sg*_|9msL~wsK0H9Zqd(gyFSa}7BM=BP0;b;k79};+OE*OAZkWDav'
        '70<EN3D&)S0XZA{lE$v&_7bFpVLz8ke}?2nQl9Tsw3I$UP279Nc=4H^bskKi10_q-Qde<3dp7Gih@>HT6ZiW+`%j8hj8GR!(pu{kx6?o0<`plP'
        'I<JsPY2+dKGcge~#e3MK2s)C5UJD@4^T5bRcZE4=aFfN1G~LXm^A+mT!bjWyc%pggywiYoVo+?|m7GL##2hp4e*49QsNW##SA9Kl=~`ymIEzw$'
        'pCsnVs@^yh$3cuvvidk7(nL$0p#~KMF}9r(bR|IQhFC?YL^8ys7ea4@?iMa1T<$#fF)pJ9+uJ1y2$=5QAvqVO7(3B?OJ(D1QGe)`GbFxvE9YGh'
        '(FZTko=ZJh?y(cY>t@lRZ3Nn5l~BRFFeBO8ht?WJkiD`9@~YQ8xq4Nz5b}5b$TPWDKEmheCSr(UM57aC7jaB)o*<3~q%}ieXNtQ!*z;8q8BqjR'
        'FkYFQ6hhqzA?X}>F)zF`(H(;*iJc;Hf+*?jk33d_Y$;$8+&L>>Vs}x}9Es@$(*l~(j;7To58z6h4yR?|ya-sCFvVfuObfD>A5j!WW&o$i*8w97'
        'Khkbnu(Zr%-YZC*Z%f{e@W-W3w-rW*r;@hB+&<HJ%sg#tUad0FZaaHzWx_GTQ<prR0t0q{)0vTnRept~RWb1y+~-fqFvtB{@)Y41q3qX}AFQyt'
        '(!t0MMRp)N?8dj`aAZ~?x~QU+KsGU<L2*y`FA+J>JCUoOy_tz0$8$OM-ZKMbE^q9N8gpLBbJx<+6(qqtNxk_<;b_J$N{;Uhq@uQ*31W1qEFZ1H'
        'q9i#;Dc&mShLMI?&=YPO#&<M3|2Yf@yQXCbTXkz%wfdQo{#6_62~fJN^~cyY0pH#cK)BmgE{N#mZLE<b2*P@bASXqHRwAJ$PD!OznXpeOst|O@'
        '(Awgg8;+2brl*D*Sc9-yb|K2N1LAlp6+yuPlI5&CCOh$#8fBhfX0}dm-UW^>?W>OS#jYF#+3Sc)bb_y4!8@%O;pe6i&U(GWzSF(B>YZI3pP#u}'
        'uQ0K5_X@vFx}3Nv_pHF4#OFv<_rg%EAc)M`BDaew6qXF@^d%7>NTnw`*>69c;71p?QdDd|_0pwi-C|)=DIS&s#u<pq!pJfKhnMgdadaD(UNxkQ'
        'NJ_($j7KR%QVe^dqKcxdSSj>YgF!v|yzad4r${HnI$)m{6<9F~!#hui!Xxv&ERvO4@f2aGY!-&xg@)p<EUJ~POg>f&MiE`ahK8^jBw~6160<6W'
        'o?=N88k=1xUPUza^HRc|ht}rs#39>{1wkqIc~tP-Guq4pSwJIcI^HObl0^ATcVAra2YlHR4W!rRp3Gg)g_9ePtccZnq;nJZ^g+(9p{;gBvozha'
        'lG_87<In-C{nD}{%A`H!c+{z=5#J>qz9gDBe>KgmJ+9TZAFRUC8MLT7EPWF?&oRZ9-iWQqUXy^J%#~r_w`=6eC~RJpB!jgQS|F4oUkmpi8~E^p'
        '`of#b-?iRA!QH$p02#$K`qzV34{nRyaB(M{53V^R%yqv1i{DyBgjq#{Sw({3b+4aO+MxN#jj+P|#rF0wLdZDv=IQ?SHhK985-j16>eo{HI7u?Z'
        '4J47S$*WD<IZknEt2yX`NDyB+<H%2FNz`}fV;*C0{?r5?F!*n@@B>h*6r<6CXMLJ)fmi+C6z@G?pym+*s(a5N89TPfLdqoaypp8;0%0ps6TrQI'
        'zyVCvi4R8bo!i(Ga*kv7P9&xH^p$`(ZDx*`Oy%+H87-rzTV<_WcxPhIsK(cwXSDFoX%{J72Tt$wMep$N`0S|ma`J!c^!*v+ry4oE+0Y-4aVWti'
        'zPZeZ9G>O;)!ySIFNmFFBj&}yDbmmkTEq(io%7h|tHUEk>F3+RxwClehUjj1umNvh4>2?tt-w%>V<CPYrQX1xqi2({yW8>J!{C?QBh-H7$0qL;'
        ')@{S`frswVqHvMIYbA$fem<8RG&gcx$)SwcEdG5!w@55jddHRP-5bNJxY8-l?aNU^>2+Fmc%6EQm!=YSm+z@e_T6OamFf{R6;;mF%xvQ3m(IZ>'
        '!kcmSNgID+ow!dkO+MuH{?px?HOr=}qvXsC+pqwYpQhP1S#f&P%$vFe6sJki??ZV5JjeXvvUhRbKfXG@{MtD_yLer<KcXZeRv&YXI%Hv+MaK&C'
        '|00fnX<%xbM3WTL*klFumWg{|;j)s&>G9;BeZQuX()M-$3xASxfAW@%<SCG1SV@U{Q3tjWhQTfF;?Hlf>kJOz#sI>F?SM%p+z`d||26S`M1vu@'
        'h#NWA-lkaThT3?%$7J?BOq3`Yi&R^}n$p2EiV_&d!8@m=^?0rXUkqr?J*+1o87g4JQ6`|50*s-3*FyTfAbqtQI<GHJ1p4T{#&U%7&yFvcZ<yG`'
        'X%q+Ff<_q%x*{%O$HaxO>&@6xO?4NKj;~(5eo;$}MR<4Q0Nde!!_bvmq<SrfgJm2N=tGSLvPnS>xL6KD#OvrN%%PN_ja|5=QHU;ON5VI!X}U=E'
        'pFAN`BfWU`1j#=!Wb$|t3zt=4v&E-Em(Cmx+C}BMg4o@Jp%Hcoxbj5+S`A7o(WL4s!i^~0+eirv77Y~(*F_+>7oqQgpb7bcNVq*5PRt#SIrgP8'
        '+s*X#WD(5g+AKl`VKgU+1F|Kx+wJP<mGV#{V~wa0q?{-ph*=dcA4t7boEF%BiAbF^!jAo@VcvVSl=KG(HDU(|rtgAi34ZcOB2`D8APE<IMsX{3'
        'f-09&$8f$#`B~m*a=cfVj^$Q^WbQ2zh=P37DM9B-(t&hl^~C(EG=C8NG>TbqVB;k+$c^zry{rOtHl33pvS9=<0s4v6@K|q7%J`M@QRe2>IVaA<'
        'rJRuzW#t;ze1+Frb>ZZxUOP*7>YN+cuNq)w`nq-;ocsOX{3})jAw<cc{U*yWlxC$V9+K#5$9u+0HI2$qLYg6R*_cY??z*bwrqTT0|1W<jf&v(>'
        'O(?%=N_ALUz6srs8w<inO0Pu<7UY_od3_r!h_H(<3;kFO*rFN(BTJ!!;`N7IK)iO*kYYY&QFA~|=v?c`sA%p@<y2ULt&qw=3*ous*|v&^N`^x+'
        'Dr^In*p{WT`mn-j?+&Wvr5{v2^~s!tVY`Zq%AUzj(&<mq=}*$>TGHvGOl%ZUfp`2QpMJFRsa|EVl1PEI#Xm`<nN%tP$B$hyJ$QY2**m*ppF8?j'
        '-K*FATI5xH4Ko%jqB!q)ueef-W&EZkJpLA=?{83IhEX*x(f9J=GBilfv<U?X6;1afgN<Bhrir$z%_GUN?Mfx<n!LG`Qadc9ns>JhLRrPZ3f@~Z'
        'm=dS1l=yHJsG{`as*+$<{e=F*ci;Ujn;@&m$0$oG%Q<yi1?c2YJ@m=km-+oj`a_^Cnrw%Jhx2J);C;`ku7@lgts-*%hwpy(AK63<tS*_&%lb}A'
        'Hw_D>(4h;T_+E;0pHL?mK3G;V1lEY&d0{YCBqI|xsdvYtu6RL`MK@Dq!uaAURZ4i{#2OM#uq7cywtfpgeD~LX?%WgkCd8%f2nEC<4$NRk7X*4X'
        'rB75Uvp!JZXyhd`SuVgIj>|tIeOr~D=`nHRf#Gr|H|ozSBt~vkL<w}&rog+!`=GiGqBjwDt%w&=>_dtiXF1ngkGh-*J};*hxH>-VIj3Fp$yu*f'
        'uY&J?^Y`klGu{Q#w{1t?+n7<{lH>;9{R?;mO3@vgOnmH83D=fp%Hom<pc4${$pR9uPm$bM5*0~8qp?HgLM!Cc2e4)f`;?D)FB|u<AHMsmf8$Ua'
        'P?#qL7hWk93DK)2L$5cbBVM`sZshqLJ%+R@=`f+e<Oqwz>0PwUc!sViPy!}7I`-+HL`oQkh=(I@j(z#4mkJpWUwH2LbEAX?NbF@BoSq-{PO7A}'
        '0#BE3ICI1-8vEfl=zvCV;fzYTuEY(&2pnMP-bS%6rn&0V?Ksi!SLl<(nE8R%{VL0eoW3ZE#}bi-O+HVxKQU|1#Qo-8SQX-n`Hf-|)iV>?m;RO('
        '8~+50>MZZybYyKNu?1vT07x{p><kTJ@-0f}WLYw@L7)atoaGi(Se|!wpnmn1-ZomJ3*G_t2qP4d2e&z!V6o@xn^Mh*EJtFsvUM!az}ZkI;09kw'
        'w5^UELU&RNz)Ad&6oT1wbP3D`(SkT+cbxl&vdBqEF3!R(gCd6H6p3<!sh6nD_oQ=s>fa?(?|T0iH+7_JrGx6SdTM=9+6j{FQV6w38qI5kcPqr)'
        'aPw$~BmrIsdnnv!A1hDbEc99>xZf9We!z0xJssW7(U?DOxy27JVM}J-;|@@`NEkbDay~pmwhzoK;HzPDC)Mu$=f86LxB;znLi$TG0?O%Fc~kAT'
        '{wir0v)km4dK}|TX9MX1n)=-;(cT8$QqYy*uUpT?G^S72Ko?vqiIKlD3cIE+3T^UN!wOIU^{NRn)~&`>@FgsOCp^5=MY+t|F5ApOx#pY67pyOF'
        'ft`nu=>M0+;Sx?_M<^^zbq14N;lHT5(yBuR-e8r_+fZ7@?JiS9F70M+d$@5MOd!(sh!INcsJhiX)35Fj3D1^mBmck$W7G*Np@;)b;1|t%%BNrN'
        'd^+3tbnJZkYX8$yWmK^Z+8XRh+uNsv4MAk1G7etcmB38xZqRz>3&}8-y@T^Ny-QAct7|q{5-Ux4EXoUi^ZWnu55I9Tvqo32WZ-ZG?OoD2u;lI!'
        'R$<?Q{|#Oc|6;D>)6I=tN+<wuBqs}l+`=JH-?h9=)V?q4@jb&(PuuyqW(I{iC)ZcT$yEN1MQ$+ZVFTm`I@YYzQSEAU%9z0B1v@|7>F%{z`x+R&'
        '<C#~|)gJSVg_k+2qc$6IHgln{KP$>!FThS(4ZqA2s~Nf_rj#C6KOk^*4l$L%n>%>d0}Nsf{7{fk`kj276yaIhLE@bUFH6qCj}xT4LhRuOqX%a8'
        'CY)w4Zsm*u{b6;o_;kH@zTB5?kVe>l5MW@RXfo^F$$n|s=cwd~Qb+iEt%1k|?36xPYcPbv9sbW&O_?;CTUOW5<bfr~qrd&n&MU*Kh~wI28+Efw'
        'Ft+Z|C_vS@=P>o5Wj#oaPWKFQKQ!G<Au6*gjE4hkL)f=E41@cZ+G!(CiQaOMKH+3ntnx|V+$otKS+@2Ew<cV(a5H0nviUciy;dUryzTS}=W^f{'
        'sO-y+BC}gNXXZ#!-LILo?dDpE0qseO9W0^ylBA2WAH?tF89JmJw<C!zqbazSUEEe3xD5{?5aqwd5fOib3Lfvg0eEYJuY-w=q-JAa6@N%_DG@XD'
        'f|wnJ{GiZPCLGoYDVyR`6`qW}qvec%caL^I8X@>|Bm@V^BJ@@t-smwV6U)h=#Z|DDJ~ML_ItKQ1+}1~P3_mZ9p<HI<gB{4xppqR*sZt09S!%kb'
        '8=RFDX)Sgyshwi#{FSp?2R*efiO#$q{r(>ro3w!A4o)Xri^NDgl?L9N)_7x&-)_AHgg2J$^;PK^h^lMpmY{i6wp*9|R_#Q1*Plnr+i6Dsaf}Oh'
        'v6*_<mLsN7Mlc<Z(1rF!$66&6rn*i<LStmSaAl5+v1iQ{RG7*J#@b%7`e)sX{;Tt={-Zrzsmmx@(Ut5S`roRENM9|b$>z&iTX`ay<U%=<zP5XP'
        'rk-W_XzEZeJ)J1k|0?!4_1^i;(D&z*K#qk%V1^ZHC>gHRU6}l^2#+`uPP(WIazqE1_~S;t#AfyM-5NRo#tcRo#U{jHWRTa4bYFAT$pbwg6HIM3'
        'O}n&%LA<+vXsxpviczL=N5bM;20?hFkz!4vLjfPrF_7cloEwxSB<(eLcd2x{umGw#F*eUz5Uu)$oG3Z>!Goscd(rDYN#h2yr6xGBXjqU5@Pz{o'
        '`tLdKg!8;<>Z^4;;Xtc(DB#JMr3I&o@t`Sp^{K$84K6_9Uga6#HJD%FwJMELFC2`jOaedBqCz?XX}=`)u2ox<juo!|Oo3ZjSm8Fqh-dZ~ap}|i'
        '<<nsCm`D*<oaaN~#X9TyF{8$Fd(@D{_11|J6U*`8XZNuIgP6;&5*tMa@XWjz%4)}*mmZQpTYoU+=-~YHqI=o<07?>)+~B?zVlfnF+f!=<8jZ@@'
        'T2n5h(tC#_1e^@MVp51waHW)YLVRWVUa73$NXjv!=bx-}2{v+OgnO_g$Qez&`K_O{tF1rN7O>}hqRA43l^&=ep;CN`^IJnn$v$Y>3d%;2%ATrM'
        'd=ImbsP$x9vq#Vn!Q@l#{^+PSdwYycq5Dl&u&*6lAHO5040OZ?XUD=$huRA+@<s!f-oR<I4Piz#e1tn_^_qrugfHX6zH^Ve>C~kyMd(imdQueb'
        '@fy-zQ{#jToix`Q=iDYWuZ#gq9NwKn#~cy{ER2EBHF%z3;NheUm$8U&COa~`Xh&s>u`t(I3K+!Ybud}ZN1f1{4ac4n?2Bk|9T;Rr>~B88tR_J6'
        '$bg)M1xO9&y{9?vx&MB>^FD))kAB{}e+ak}n5++XL@v2&)M25lISW%J%pCSKW)P&2BEv%=iljLB5(JiZWtw7m{^3!Qkpq%zX3IAQbd&aHV5A|n'
        'R7N7y8MY{Y<2JYy@Y~R12fyUCjBws~O#Di+hpA4s54~fDD|S>L=Z!A4=q!4--u&gRYpsB6gHyLFf`C`mH-W->tC03yYaO&CB_hj-y<HPia;E3C'
        'vH&5gLshp7I$eOag_sGXTtv?GmGIK`o<7p{F3B-kZm^8~HEwaQ&Mk75yfqGyL+cth`RwsFx!zIMv{BYV0fq>ir-G{W2ZW%wdPSHt9%Lds^S7li'
        '&j@(zU>5Ms7rwoXF{N00vc2t^{e8rHzi;O@S{Ocp`8s3J<yUg!=YVY)ZSdi}V@R@$j7H&1D;PeTd7+e%W3L)=&>L12J<3#b9Ryix6uOBD!395B'
        '1flTR3`NRhjHR(Ql#HdPl$ePhRiI~Mf0C(m>?jTP57W~zjZkt@FTV9tVL1>ZZW#z%^xDupva|rJ&@`mY%q@e^;Q1YI`oY=x%DE>Sf3S}<x-YG;'
        'h7cj^9mrSjZX|+~u(AT-Gs__v+vMaCL>f256Nw~dNjSMjgq*on9cf+uD!Z_io>Hyvnw@?3BOunij#(>1FHzT;Q9EP$H6yoF{$3Nk*Bxs;>EI{y'
        'wn6Vl5=ZhUU8ldC;k+(QlWlS>CraKPxQ>aBSP9pfoHsD8GdWp);jLIe;t%c9N%mH(tN_!G%-fU$@nia&if5_wJgv9~?l2y658|oo_K=W^J&2?C'
        '77?}gW*&Bmr*-!$dOVT`Ow`TV^Q_7(<7QgRAJNv~thuSP6ru8Pf>nS~<zoNXfI;+N1dT@hu8Zr!ZGG5PfnOC-#HQ6w{Qz9|7XJ7EXh2oO2J0i8'
        'Rb7KWAoX0=Yxj?pfc`k(@zK)IkIV`DM@dG1Y%u(gl=MvyQQ&-BWb|E?b^Wo^&>sOXK3W307VLhao<C9men`@38-$coP0n`mk;f!)6pk~P{1_Hq'
        'ks7VJzcu%0xzD;O#+umoF>KO&t5sj!XwCUR5ht;>a<pgz)UTvk0{84^8jOA7S!`%rEsKOXw?#K~pm1HP4IGQ}QgFKTpl;?OL!8vrL1J5<I0q-a'
        '?%C^$I*J{V%@qZL@t+X6hLeA+Q(>5v56o=HBLtxNaxqB#*@9evVgzB@=GOlY69Rqa'
    ),
    (
        'c-rkfU2h{ta_{^VjWKW{WiEH^^&x=nxDKtQS46auLUMh%=mdI1HpQ`rGxW?*TAd)^9u7f(JQz4TFc2UxaJb}<d(ML&@@xDD?tVi0V`jSgYd%P7'
        'z0PGHY_X@ix~jUms=B(m+gq-}C_(WTzL(&qjd>I<(aKF0zITZ{{_TwX<R9kPP1X^PJFYiz1J}Qey*R5C;b4ZN3HZ`Tzr;y|-6esK+?f1mG#c-q'
        '?iT+@^TX4Vj|VSa4SVCk>B+X>8XxsW{mJve5Oo=?&B<i$`FJvEbqKAYe~p{1&dMbOCXMI4aWAc!w|b16nVYx{`^ZYqdgCKfBd<(qxY2Y$I6S5N'
        '>&z~lU2x&7_oAP&Vrw46Nhik1WaVDr$utb+-c_@K$Ujz)c!`g@P7lz4`q!bqPP{NcquV&aOQ$XBdjvw)`OCLoe)H$=zDz&(?rpeEy3UO^!=$Ly'
        'P(=y=pDesM38Pz8whUDiDA77dyd{>ZDo{*SEKpY73j1ClAgqH)gjZqg(XI)zq8LZpk7Fh`TMyz4&(RebMZ*4o5Jm>4**aj{7bQe4)5+dR3!9SM'
        'wv_svD7=}>-6<On(RLW#u!<2TEDJ#W21kR=h)Xxd6a1PCRGi_FR+oD0WK|l10@B#Wu@QTfzy_<5M7O*y>m|I2NlicmevPN=1UK_4^q=E6((h6K'
        'xPLfCfxE;~`NzZ4mnq?srAvf8l0N_9s6XtZ<aUKgpL-1RJ*mR!@OgiTKKi8&8Dh}t%yBYZxW1p!1Q>QsNIG|Dd*=ep!-$fIyns=9!E4VwqIZ43'
        '1wj7P4`Zw|nDCKEdXxW6fp5xhRS3-do;xXr4^Lm6jGOx{)Egm&0%!60oxtS&LgP#r5E9NE*1)MvGy^fA{Azx&#?ft?sH(_a#@%LX=TathAdRa!'
        'tTT_yKLV(=)u8S~1EJpGVShB*nG(tsrH9q&55}TlnhIP@B-!z1ZRt0a5xFD|*U?ldTSvZJFeR=?f@c#qX-KmhBHPgBtvA!qgmWnl+*P~?lLsIZ'
        'SR3`zG+ZvdWU_GMh5X?fM=_BPxsckkIB}ONnQqCX=5*BN0KsKNre{D{kO3k1c27tdVF|15%@O#7h~r4VYC6QkGrO*qicI`tf+4!qKk9On@|M#x'
        'p=w<>27+F*qK92V-f23&v156$(yG&Gq0vSkw{ma@yXeC*K@mMdxoEfAngm7Icd1s37vAbeCqyRI!zP^@5!&=}NUTM|B!2u@gv`VT6A$e47tsDd'
        '0=Tv99QKddGIVq_I726=!<W6|!9VV1VM-@Q5JpSa_kN9qk|mR6j>&3fiktagZ7^rSY{|b{=L#*%1SG55rE7KpI~5?}CU_As6=>-a5#sI%aa!_z'
        'sp}$;I1oN8!6Prvo!D+yba<dhN9s)~O)@M5ANT?cJ$gpg?QAKgQr#gYFG}JYkF4q)(avcB?Bex&?!86;opT=tO7#m-KOd0UByTFK8D1<Eb%-JN'
        'T{2+K#Azc3IW74!;kUPHDusS{gCkG~mIc)qFROXV#dK)x1}|qe{MyR#ll8(}fu3PZ2Ula$fk6$*1I=KFF5XE;m5#4E=5HM%3Ls6iWuI|$bx}c7'
        'R3?sIg|L_N)Ci<ii___+T=;=a2195y&)G~8Y|j@@CYP|)Q1yRS-`)f7Kp;aJoM+1;x@ZCo+3E=bg7cgiC)6#`s8&OD?r;dsg~gAG+oqYy?cX-t'
        'atJlM73}J`s}&Arau0W!h&bNNIZ%2gMHjmF;()=?n!s<yww#9tR-Y*&_rU5sIhy;RVxcv$G}G#tFpk`tNse_Dfyi6slvEkddyBs&267k9%2EIL'
        'tUuh%B0nE$-@U|sK4mkFkm4`oZtjfID(Eh&e7@(+_Ac&`18Oy|!RK@_OX{?xN}vi@2$O0pd37qQyzNvMBuh*nYDP4x(b6n>fuSmPl!)UN5SB4N'
        'jSC8=OcLkM@vV_Ilcu$*^@hR0Z%7guuYIb@Vw_|qa3c+Do<+LKG|wB!u}op6-Yp{7q^&i7H;tYpUa-b6zDjB8xHCmT>h_$DGw&@Q+_te2N5E34'
        'Wtrw256jR_r~}JX)?dvSTbGJzlSWk?|KpY$BQI)-*4EaeH#|HVjQfY<S7arA)bAaSkI-T7`0!P_0^W&PnY#XTO$f!xejj#yvWnY*{@&qi5!NMU'
        '!u*3;1qROzCSD+6lD9oTPb&0FDN!MY>tvT8y?}i3f-4)$^NS6D5*)9>T?4%)QlZGiwyTfb+de7>DiLMsi?mLA+N8CCEyh&_tYKQD2rLK&Ty*8G'
        'dD%Iybb;ROqW9#5cPdF)jSP!a-x@W3kcqV36)8OD)eL=Q0+!Xt`byPyD%x@AvkfLmDaBz#$^>uD%_}(>pK>7u#HEbN>#+FR6RDOP%yJ@a^}w2h'
        'xE)=ht$2i?ZB}|qOw`#_oe~n(D(Mmx#l3;qqjgzzQG1v*B&)C-h+(<*u^T+{0#Zq1q@^<9Vp?0~r=j{dOk5uw<{P&$Y1lL_QMJyEwca&!t5s~3'
        'tS%Sc)dI)KBsUmK_cd6mvC<Bi=WDuoD_{`=?Gk6A`$Uom2#nhb4H_w~4NlsSmmoGxT7p`}3&0)rTbolX_-CC?rMU6FCX4lD`NY=Ze&zkk)0tC5'
        'W~e+`+O$>%^I6>)opS6=P?ZmiN*4K0NEel>XZ2N8CP5EPn?9i{OJxhP0whw|xB;fcv(0rk&%5a&y4N95riW;yx<yU^>`B@j-~b4=!sfcyIHI|N'
        'LT9L(D9fg*IOI6@W3>a5ivhb~dd}PnP<GWjq5s8xjEjhRV#nl(C7|ReJwnsPOT<V!`Zy`^My&<!KR0#C7s;-HZ<(h>K4yP{ubFQ|zGi>Iwz^Y9'
        '!RV!J6Ax00FL5C)1NCL@lFD*{r6#9VDFJn5#Y(Em1(uo|s#0R8D<(3iE(*0VV>&D!IQB~)Jy<FGDe+a(h>WXJNm~jsipBVJ;Rb|9Dd+hty2M03'
        'ioBsbAHba_IFgGqZ!T>jxyNdZHpf<n4>b($r5Yp+BMH!Krh4pZOT)7Kkxq*oNLz;2cChBQ9Imm;6zn?S1F-?%pA-U4+o@~ara2NP2PGwqX&E%3'
        'GNs|$zCZKO>fNzHws&VhM;~gdwaZ4^4&Mp^j=2@S81@Z&_(@q0x*1ZZ1=W;Fkz|Ned1r=5Ed(u0qD<PDirXqy5*aySQmFwqwUx2lh@slj@<k}m'
        'ogE55qj7KiYDYVEi|}TWXXeL=o2*&RYJ*2CJFz#zmu}Qqy3yye@Fr+F@4WL4`pdW9{Pxe^eTkl@4ISa((cqCG(;q}ZbC@`aLM7kA$sjT~bK<AW'
        '9Fq^nMH6ITgJ>B&CXhyPvoiz6?&I}zieoh&FlX}N>B&j|aNK|HSmIQUIaAi53j^M<l5PUo$!w;+Ldf?+V@D4gs7d<fJ#7nCW#IsYHZcFTqUTV+'
        '*_0rFN=+i<DY_LMLkZNTq{s->rbZ;BZ%Yh-v^gyRNJUcc>nUC(sL%dKSF3J}m=>t4Am&0t@P_D){r_H?rQ7S;(@*-tPX_&8>`uuNvl3l<_y%fM'
        'c8U%p-KOW`Q1P)kXrl>`Ts0e$clY=6(Y{6B|I_bKo^e5ci0R3G4vmfi{UTxXB63%YyuBNdbz8uG9<d#{{e9EPfE3%AcTGk&YSywC#e$HVii2MT'
        'zX}|s+NXEY(X#tbOAQK@K-D%_?Lu}8$ZmERxXT50DcO!{GN+;c9?jJC-)H}Q%KrNS%SG&vzt+njZhnx~rS2|kAjQFXAV%hnI)&xg+EPPRHr*oC'
        'qj3!oypWBmN!JwV86^av5cqy=0vj9IL7fp*TJ4HGHd|lJo2T^$A6QVGVxy(sk}|8+FDC7SP2?I{RFhzvU4X46+wKmSY1CDptQWX$M<4s)jUy^d'
        '!x@(Ky3pnguA9GVNV+)_s{HGrytb!Bx|*k@CnB8|LNs^7OhEoAw<*FNn456}ArSH6&(U+7DB*4Cl!i|hRcrSOcbx>kPMo%4PrP6r0uGHAUQDb>'
        'ytoYAXhzh!JBv}WAl?EsEHoKl^!LXEo!sJdKn|fZAeJb^Jda`-&b;|;UXOs9hS4nUIJ-P2a&|fzj8BJy{tj1j>M2Xv*&sf~SO1BIvN>o-2Mawc'
        'GO!^i$zsD#va!B#qku44nK37!+yOJ#ohr8YCi391;kh%Ur)+s8JUbvB&K=!_fY4j_`}>;XK?ZUjxl0V=Nur4mxEpVlEV>T8qav9ufFv%+?45YQ'
        '48QJ<qcz^)fuYe!?`(8*I^LlaNGDKr5%>-nwMH%sdGk~f060ku^74u@AmHv?0CLb3M?bIsgAV=S>C3azlm5vr#~x(6nFjxl{{{U1w{O6+ux-ee'
        'h_RHt<@9`CfOHP@Y_~AVzq4c$6S_(d=jNk~N)Ef&Ri(~(mTJxpM5KsgpUfsa;|;k7&&w`Dkf@NmebB}c+tgIi>aYy%R!g>cStmJ>-2!@Klo}xC'
        'wJ1YUZyrOZqE&Zdf@6s4%uI#KctT4v?wLpd+^Z`Qg90!GlYamW08fkV)D3`XtA#;_ufLJ4!B7uVy|r3m>8|7~TiX#7b<V<k4x`3^YGr40o1iPt'
        '>nu4#-nNfrI12aqNoNSN%9NMZ8x6qy-0d$Icd`_5nRbzUZQ({|*~iRl_V7${tB2W{wiw0h>4HZ6K2?uzehM475%ss(MO!nJgv@~#IfN|x=2LzW'
        '^wW-nr*tH6t32*hkVX3{nn~V?W1`IDE1|2BtfO+_o_X=gcW)=@buvZC#YX&K`>JV?quS@$#&yoJX{%;y#$)-hy{bp|xa^xsz4;sIhQ$?}?|<{P'
        'Q#%>cY_Z_LZeg<uv;iC<G+Hm0ZglI&>0)xcQjSzU%{QmLFV;9cBq_Ua?Aof4n&b}dI)X$(9h}1C@@0TIRu2kQfN6@TZW8mMZVv3DRVlP-4GeO&'
        '8Tyd<+Nu;JwDrRIRnSYyX-h9OEdP4t2D1E&i0gqO_XfsIbfW^WqjgQky=~WvSfX@>$&x~s$+ONC>wMXnpC=uadNJ&s9qrE9lfu?lG&Wc4@%`&}'
        '+BOr5=>5O5_hy_uHbf8N<yBkQ*-m=y@E}~t(#|R!>gsM22g+jHpu9Wg9B7s#IHAKx9j`|D9Uz+?*Mno0>RSa1nq5uB30VJW(xKOqGMOs4$%GSN'
        'PI?PMs^ezNeu9_@(|YYZu^k8NC5~LUx;G=K>GKSJmeP;r4lTN49o##-B7wbhJtDncz~~f=<}(A0)7@3z`DUn@@qohR&M~~uh23JAU!fwgZO_@0'
        'Er7G<81K%I5H`Bh^SwKn^!sz?E=T3wx!BWOJdA@0o?S5xynW~A(^G&MQMHc`R&7W*pzZVJtV~bVwas7CGk$GLh86=&wS3O$GGs(ec8;6=RZj|>'
        'I~DbN^ytwu<XEevG~8=SE$fZ$0TKo|zY3hrXQ2mH;1WLSay?f=o$L2Hi)87;KpjXB`8oae4E!Wo6a0*)k+(|NUAA3^tnSx7cEsoO7UUEWM3qzi'
        'ZEukzL|7j`p3Z{KXYmaC-gVRoaPl}<Egz>%{`S2mkBQ@)WWPH&UUrsV&{=*K@BK_;Jy~~qiO1|w^X^Vbd~&1YG&m03*#Sx<_l=M2bRBug?J>T_'
        '{sG$a!!X9m>`xYWiOIM0oR^rf_xG)z36?zOJONC4%$X(%F2mU^_&)Ql(bRY2n6Qu&0(f`_2l^fWC9Pl|3e3myxJi4a3+!DjlJ4I;c_PXP(xFcz'
        '<;u7gEZUnEeelGe=j>|p+H1l(Yb|R60a%_W7GS$2SJ~oDD28f_uIwmFs@ml%Xzi9%(P4E=0qm6wXFPSIS+nrM2!owa`ribmc3(%ul!`&dvBI&>'
        'u&KW&1))LiW0WjRxr?rZ;5Hc)0mx`F%<;I*Vse|s<*LW#s>kQ*1kdaNv|6#c-E~<Iw==}<<oI3X(1Z|+w<bc7r6I6Q>E3WK+R=rjQbGdLdpt*|'
        'WLN69$dFf5FZ-3Z!zj54rHidW3?c~;VJdM1=kOT8Bh;hkN09L}){q|(F@JoOodYp{=3s4Selp1B?`k$}h4_q|7=eC{-mkI@?<J(6OV+@YZ=xH%'
        'E%U|Ni*TK&4U198%e>M}_ToUzh1x?He!i|78mbo*5<ZUX-MnAm-K58_io-~Z;io>aSSZ#5N(M%@m1I<^44%k^EXE|}*@PqFRPvDcp|I2i))r>('
        'sTr0~z)}QT=$TT_o?yv)tH7ZXe6tmYB(jRR#j5JeQcf|#*c_L?bK}56ft3#?7C``ffdEp#EHbFz10tQgF{>o^D5a~Ia`6HDZVsl3#yDKi^%T<='
        'GjGnedqH5hTv>3P$qwumo-dY|&{o)$m2fp;JIJfuKf}8|*H1TAx<A2qs@K|w;Y?(uUMz=vt^F8JQda88d@8ntX|gY^^y9nB%bAOa?Om#lC5_L~'
        '^7AJbt?cIFwz<Z8rW&nwl_R&Mqw#j2Z$HsnVVK_z5-f3pd`X86Ipz->K44CkVfCoa@NHuTOnMCc=(Bvgt=inDG)6=8nXdPi>e7_e`Hw<pMl?}S'
        ')Ld?cBtIDZ?e9|;_t0=`Qx4CnqoJ&uwVf5czPb$4a}wpK>!1JUU(j6+;NFmy0pil^8W-(srRmVHVe5+F+Hp+FLWQ~S*I@3~|DCT8%Gs+6VHtx>'
        'E$XuP`+xr38)9*aZ2^-DqCsoJDou|8X&f?5Hk|?sgXT`x&YHTRSSeBG4Qf?X7AZA21Upf)r5ziM`Hu8%Y3CM0tand7r&>7ut4IZBl{eA9L-Sd4'
        'lL{`1UeYPh-2L-L%JFca-ivV2A>r5h64lygl~h1`MIID{bqjS{9h0=bf5#bmzrWAUQ9G8(q$1}qt!S&%ywiA;U4g$lJuG{uW!5ee_03FOB}q2U'
        '{vS-1t6=kgQJSgs|IthHjvR}U{Uu!(H-0M(7#Z0~DH6YGqE{|Wl|-&g+*);fs0spBDqNKWtFBLGxwfO1zJBf)E?3iU-xTnytGm3$yXIAG!IgLq'
        ')s5k%vC^(&Ps!Mup^EjcxQFdeaBznG#MQbnbBFKhSV97})XTyiEJQpiaDi<*X3Wxl#0Cz1h<YsQ-KxFYv2iMgQ8MK!j1gUh^+k(`ZPGk!5@kY3'
        'A1>2{4>G3*%T+{1X9-W;dY}xX85n~jAm=J?V@pCaO60u|;%409J!tNfZBejU@3J7?OJZJ#1HWQGi>%X2kKw0HkyJtnN=8SFZZO;G<ncWNda#27'
        '$)tlX)E1j7Dn7~F`4HWKn)i<BCgJSV8N=PjZUlF<U0;@^8M{=2Ix#kJOk)P=^&5oDRt4Fs8I#NH_}qC{M67rtc05=_L-zLp0!4wS+EFWj#3O)2'
        '+N=nT!im6kjk(8`d1;2HiEQiIx7ZV_>WIB7EzH263g_&@a@VZ78)jeR)gF=(I6vY+c_a@C6!M1~mL|ylPc)SvHfa^*T~Ng^XRKfh_tzejAJvt0'
        'XSV&EsZHX~CN~%d?BsEF*v7V>{UEPsJ<!>(^v$e-#H;WB{SVsNFn(=Qz0@mq6VuAQ!eU21rhAF&l;zn=F*IkKvRRBT?3rcBb;Rm$kf7;0qS*!h'
        'Et&7rbxfd=HP-$<@zqu|y_v~Jc7yq~m)!2}cK}kD%ru(Ew8U;qI$+ka&E)A86S-R_;gV&c&OG-j2nqDgHtAP?&Bx=|viH~6l(SRym>ieZ2RSFl'
        'K}-22rioH^%1w_Ayn`NX_%CffK0QOn{ZIPG=w*LA92}0e1zR~}@iKi^p=cYa?){XtmxY}1=h~AO7Y~--pY>>XIOAfg?V}!lMFM57L$%d~Qrh#L'
        '^4!GU#X;x&`Mp!=qQvd;=`}wfMai5bZhE$(QJhz;?|^MRLHhr2cHBE*cji3g)cD21O_=@9EEO>sLEX!D`72_?q3WVwy}ZN`3g_arL;1bDhSH8m'
        'g3>U5(a_$IKP@I+@Q4|RIYWcLIYi-tCO!7fNcI6Nt(NXBaf6Ucjdn=-oMF0-#=-P9Z@VJMBpnC>9)Qgt5YAqE#9R}kJtB{5^3`fow-%24KDAwI'
        '&uSrHkm&?m5Q#+bM4md=3{TuZlSTZAwD_RP0R!ztoUKk57<N|5FX+l?b+28|rx&m4-ptk`e)Q@iMAX6YFGqtnJlH*H4RJ&t&)HoDM$zWzSO0;I'
        '_~Sq*eWuW|E1H=$_*&3~zBy*SDL#eXwwVd_Ii!nr(YB5jy0IA>318{!#lZ%flE3-=mMKZPm}jDHQRM}RU-h=ZzxsnT($tHnFx2^@Pj$yy_fl+w'
        'O>6FQv~!f->fyE+;KJd4S|{t_8}u@abK`+$WuvV=-c@J7;rpZIgASf1+ts+M$iLM?Kh1^&Y#f*eert<17@Z#X#{K8;a@aR&*i35&>24Qsx>@sK'
        'tZM|}#bi|~1Vqx^r2N?Lz35x!y(8^yiR};Dv1&;|4G5J5TEG9dKb0nP>i&}X%^_+>GOEC?l%0sJC2Tkt{T&(&UJ$qG4U5)DL;y$LRp9!{MU%Wt'
        '-V1FuN-Yt3)<r+na%@s)#w|d@EI$GZA%jMAdO&IxZj63PHx8F{`#iS`y2^2iO+`^O-R5NNmRO^IS3qm-^6ZpWEf`_78l^#qi-z81_AKre3>)ZE'
        ')Wo>c0Oza%lX>A@(>rxcOv@QcnpJc#sz{9%K$G4EX3qx~1ir*8@LRC#xfctw3B#)<#(}qp*kcXoa!oH2Qg-GI{9~K-24!huRZ4`Ci^ujs+5`^2'
        '-GwG@(FnL!x5!$FjWi1E{$PI}-2s4GTZv0I_NH(XCB-6Fn~F`eab{=1mZRRui#{<VCx?A>Htc^gIDIwBuMv2&h6Oy6MJ5zRXA!>k!gZWqA|S8L'
        '`6d#NcF-6bex2AJlV^1_7dO2z4Q`hhZcS6S58~qYhva=3ItPtcUy9j7@4s(1Y^p$}(u>7)`Sc(4f@C%rr@S%B!*=&P{<O;6i^y!vLp(XkZB-m&'
        'c9V0IUKWj3*$Cx4OnB_bjSO)jWtwD-O{b}q8~tS>AAz&!7Y2B2H%WsoL!_fq2qfQKQm*N%w%269saUC%B`6k}1*z5}l?LOoO@?4KzUGH}i_tUL'
        'qS_c5fRrPdMInmuQ{M`&kDLmj9J6YHL|ZViJPaTo&Mk-q6zs`WOxaW@Glj&;@HL!#D?qt;Q?Ghfrv>q+H4rb}4y?N+D5FkVO7eT~uA#boFOhbk'
        'KgS@wGH1p~)b1@*atbs>*}C6#a!mg6;<!H=Kft5M30Ybd-$eAsKjkkSqcN%N6u*NaUZz~R$>KnJNI`njjh?QT9;j>?F43+3Jf^@Qf6$Dz?bLiu'
        'S%m2F>x8oc^;zYuo>LAId_}KkqzM^$4;}m(PuHqD<(v(BFJAUUo5^&6r=J73ojKjyBKoJ<I)8FuBBnF-!x$?R7-BunAV-XKa^P6*AD0I;8`vC0'
        'qs6Z9RJHEsa_@^(w#K#?tfCi!3(^PgSetvNKyegeg$}8X-4r)=i!7}`Tu~?f!Y61>V*JILJ|5!ehtc&5T+0Y#NsgE4+RT&%d8a-x$^NFP>)}o8'
        'Z1JeE`3>7_di00G)8PTSi|{IHvZ}3JKWRJ~Jnw(h8*Z&Z%}>UYa`A98Sh0appje#~_u9K+#@1<&S}aen3*UZ@+?kgyI-D0|-4Ld>3`Ckw(-)P2'
        'm9srLYkX_foP%Ud6><#M<r{i{ch$kh191+_1~W~wY#S^IGdtFHM6rj_twaP7U2ln{G*0rJ2jbg}-8@`%`f5Bld9k%X35!FfKbM3q7+sLeE5D<i'
        'tqWl*Y5bLzrq?Xx)<Q~@rdn>N+ztqm(hxqyXT}!_n})FTgqNwkK_(R-rl%o_XovD^;evF9qY*10><7Thpa*6rt~YVhj}>T2=R^@vSx&PFmOOzJ'
        'D2fYMj!Qbvbdn@=crD9#o93kkFXFW%xJ|>k;Phgr14J4K@xD!;)M`=}g!z@v2g8=+f}}Q!TiB<aJ~cS1-O_CqcypasG}$Ww-D(j{kbA3@?@gJw'
        '7XklYZIG1+'
    ),
)


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
