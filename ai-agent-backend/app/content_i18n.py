"""Translations for *content* strings that live in the DB (seeded from
``seed/product_types/*.yaml``) rather than in the code.

The static UI/bot strings live in :mod:`app.i18n`. This module covers the
data the configurator and recommendation cards echo straight back to the
user without going through the LLM:

  * ``spec_schema`` field labels (the configurator form) — ``tr_label``
  * product-family display names                          — ``tr_family_name``
  * the broader family-group names                        — ``tr_family_group``

Design notes
------------
* Lookups fall back to the original English string, so an unmapped label
  or a brand-new family simply shows its English text — never an error and
  never a blank. That also covers the dimension-letter labels ("A (mm)",
  "L1 (mm)", …) which are diagram references and read the same in any
  language.
* Units stay in the source string (mm, Nm, rpm, arcmin …) — only the
  descriptive part is translated, matching ``i18n.language_instruction``.
* Label lookup is case-insensitive: the seed mixes "Frame size (mm)" and
  "Frame Size (mm)"; both resolve to one entry.
* Chinese is Kofon's home market and is kept complete and authoritative.
  Other languages fall back to English here until their tables are filled;
  conversational prose still adapts via the LLM language instruction.
"""

from __future__ import annotations

from app.i18n import DEFAULT_LANGUAGE, _norm

# ---------------------------------------------------------------------
# Spec-schema field labels.  Keyed by lower-cased English label so the
# case variants in the seed collapse to one entry.
# ---------------------------------------------------------------------
_LABELS: dict[str, dict[str, str]] = {
    "ZH": {
        "300 mm lead error (mm)": "300mm 行程导程误差 (mm)",
        "allowable axial load (n)": "允许轴向负载 (N)",
        "allowable radial load (n)": "允许径向负载 (N)",
        "application tonnage (t)": "应用吨位 (t)",
        "available speed ratios (drive)": "可选速比(驱动)",
        "average life (hr)": "平均寿命 (hr)",
        "average load torque max (nm)": "平均负载扭矩最大值 (Nm)",
        "axial backlash (mm)": "轴向背隙 (mm)",
        "axis 1 rated output current (arms)": "第 1 轴额定输出电流 (Arms)",
        "axis 2 rated output current (arms)": "第 2 轴额定输出电流 (Arms)",
        "axis 3 rated output current (arms)": "第 3 轴额定输出电流 (Arms)",
        "axis 4 rated output current (arms)": "第 4 轴额定输出电流 (Arms)",
        "axis 5 rated output current (arms)": "第 5 轴额定输出电流 (Arms)",
        "axis 6 rated output current (arms)": "第 6 轴额定输出电流 (Arms)",
        "backlash (arcmin)": "背隙 (arcmin)",
        "backlash (arcsec)": "背隙 (arcsec)",
        "ball diameter (mm)": "钢球直径 (mm)",
        "basic dynamic load rating (kn)": "基本动载荷额定值 (kN)",
        "basic static load rating (kn)": "基本静载荷额定值 (kN)",
        "bolt holes": "螺栓孔数",
        "brake release pressure max (mpa)": "制动释放压力最大值 (MPa)",
        "brake release pressure min (mpa)": "制动释放压力最小值 (MPa)",
        "brake torque (nm)": "制动扭矩 (Nm)",
        "braking torque max (nm)": "制动扭矩最大值 (Nm)",
        "braking torque min (nm)": "制动扭矩最小值 (Nm)",
        "built-in driver": "内置驱动器",
        "communication baud rate": "通信波特率",
        "communication protocol": "通信协议",
        "control protocol": "控制协议",
        "debug protocol": "调试协议",
        "design life (hrs)": "设计寿命 (Hrs)",
        "direct drive max speed (rpm, i=1)": "直驱最高转速 (rpm, i=1)",
        "drive wheel diameter (mm)": "驱动轮直径 (mm)",
        "driving wheel load capacity (kg)": "驱动轮承载能力 (kg)",
        "dual encoder": "双编码器",
        "dynamic load capacity ca (kgf)": "动载荷容量 Ca (kgf)",
        "efficiency (%)": "效率 (%)",
        "electronic limit angle (°)": "电子限位角度 (°)",
        "emergency stop torque (nm)": "急停扭矩 (Nm)",
        "encoder type": "编码器类型",
        "extended temperature range (°c)": "扩展温度范围 (°C)",
        "fault stop torque": "故障停机扭矩",
        "fault stop torque (nm)": "故障停机扭矩 (Nm)",
        "flange bolt circle h (mm)": "法兰螺栓分布圆 H (mm)",
        "flange center hole g (mm)": "法兰中心孔 G (mm)",
        "flange diameter a (mm)": "法兰直径 A (mm)",
        "flange thickness t (mm)": "法兰厚度 T (mm)",
        "flange width w (mm)": "法兰宽度 W (mm)",
        "frame size": "机座尺寸",
        "frame size (mm)": "机座尺寸 (mm)",
        "frame size / model code": "机座尺寸 / 型号代码",
        "full load efficiency (%)": "满载效率 (%)",
        "full loading efficiency (%)": "满载效率 (%)",
        "full-load efficiency (%)": "满载效率 (%)",
        "holding brake": "保持制动器",
        "hydraulic motor": "液压马达",
        "hysteresis (arc min)": "滞回误差 (arcmin)",
        "hysteresis (arcmin)": "滞回误差 (arcmin)",
        "installation direction": "安装方向",
        "instant max torque (nm)": "瞬时最大扭矩 (Nm)",
        "insulation class": "绝缘等级",
        "lead (mm)": "导程 (mm)",
        "lead error over 300 mm (mm)": "300mm 内导程误差 (mm)",
        "length l1 (mm)": "长度 L1 (mm)",
        "logic supply voltage (v)": "逻辑供电电压 (V)",
        "lost motion (arc min)": "空程 (arcmin)",
        "lost motion (arcmin)": "空程 (arcmin)",
        "lubrication": "润滑",
        "lubrication system": "润滑系统",
        "max acceleration torque (nm)": "最大加速扭矩 (Nm)",
        "max average input speed (r/min)": "最大平均输入转速 (r/min)",
        "max average input speed (rpm)": "最大平均输入转速 (rpm)",
        "max average load torque (nm)": "最大平均负载扭矩 (Nm)",
        "max axial force (n)": "最大轴向力 (N)",
        "max axial load (dynamic, n)": "最大轴向负载(动态,N)",
        "max axial load (n)": "最大轴向负载 (N)",
        "max continuous input speed (rpm)": "最大连续输入转速 (rpm)",
        "max continuous power (w)": "最大连续功率 (W)",
        "max continuous torque (nm)": "最大连续扭矩 (Nm)",
        "max input speed (r/min)": "最大输入转速 (r/min)",
        "max input speed (rpm)": "最大输入转速 (rpm)",
        "max instantaneous input speed (rpm)": "最大瞬时输入转速 (rpm)",
        "max instantaneous power (w)": "最大瞬时功率 (W)",
        "max instantaneous torque (nm)": "最大瞬时扭矩 (Nm)",
        "max linear speed (mm/s)": "最大直线速度 (mm/s)",
        "max motor shaft diameter (mm)": "最大电机轴径 (mm)",
        "max output torque (nm)": "最大输出扭矩 (Nm)",
        "max pressure (mpa)": "最大压力 (MPa)",
        "max radial force (n)": "最大径向力 (N)",
        "max radial load (n, at 5mm from flange)": "最大径向负载(N,距法兰 5mm 处)",
        "max speed (geared, rpm)": "最高转速(减速后,rpm)",
        "max speed (m/min)": "最高速度 (m/min)",
        "max speed (mm/s)": "最高速度 (mm/s)",
        "max speed (rpm, i≠1)": "最高转速 (rpm, i≠1)",
        "max speed direct drive i=1 (rpm)": "直驱最高转速 i=1 (rpm)",
        "max start/stop peak torque (nm)": "最大启停峰值扭矩 (Nm)",
        "max stroke (mm)": "最大行程 (mm)",
        "max thrust (kn)": "最大推力 (kN)",
        "max thrust (n)": "最大推力 (N)",
        "max tightening torque (nm)": "最大拧紧扭矩 (Nm)",
        "max tilting moment (nm)": "最大倾覆力矩 (Nm)",
        "max turning speed (°/s)": "最大回转速度 (°/s)",
        "maximum acceleration torque (nm)": "最大加速扭矩 (Nm)",
        "maximum input speed (rpm)": "最大输入转速 (rpm)",
        "maximum speed (m/s)": "最高速度 (m/s)",
        "maximum speed (mm/s)": "最高速度 (mm/s)",
        "maximum thrust (n)": "最大推力 (N)",
        "mean no load running torque (nm)": "平均空载运行扭矩 (Nm)",
        "mechanical limit angle (°)": "机械限位角度 (°)",
        "model": "型号",
        "model (size)": "型号(规格)",
        "moment of inertia (g·cm²)": "转动惯量 (g·cm²)",
        "moment of inertia (kg·m²)": "转动惯量 (kg·m²)",
        "motor center height (mm)": "电机中心高 (mm)",
        "motor peak torque (nm)": "电机峰值扭矩 (Nm)",
        "motor rated current (a)": "电机额定电流 (A)",
        "motor rated power (w)": "电机额定功率 (W)",
        "motor rated speed (rpm)": "电机额定转速 (rpm)",
        "motor rated torque (nm)": "电机额定扭矩 (Nm)",
        "motor size (ø × thickness, mm)": "电机尺寸(Ø × 厚度,mm)",
        "mounting hole counterbore x (mm)": "安装孔沉孔 X (mm)",
        "mounting hole depth y (mm)": "安装孔深度 Y (mm)",
        "mounting hole diameter s (mm)": "安装孔直径 S (mm)",
        "mounting position": "安装位置",
        "noise (db(a))": "噪声 (dB(A))",
        "noise level (db(a))": "噪声 (dB(A))",
        "noise level (db)": "噪声 (dB)",
        "nominal input torque (nm)": "公称输入扭矩 (Nm)",
        "nominal output torque (nm)": "公称输出扭矩 (Nm)",
        "nominal torque (nm)": "公称扭矩 (Nm)",
        "number of axes": "轴数",
        "number of circuit turns": "回转圈数",
        "number of stages": "级数",
        "nut length l (mm)": "螺母长度 L (mm)",
        "nut outer diameter dg6 (mm)": "螺母外径 Dg6 (mm)",
        "oil capacity (l)": "油量 (L)",
        "oil hole thread": "油孔螺纹",
        "oil volume (dm³)": "油量 (dm³)",
        "oil volume (l)": "油量 (L)",
        "operating temperature max (°c)": "工作温度最大值 (°C)",
        "operating temperature min (°c)": "工作温度最小值 (°C)",
        "operation temperature max (°c)": "工作温度最大值 (°C)",
        "operation temperature min (°c)": "工作温度最小值 (°C)",
        "optional extended temperature range (°c)": "可选扩展温度范围 (°C)",
        "output max axial force (n)": "输出端最大轴向力 (N)",
        "output max radial force (n)": "输出端最大径向力 (N)",
        "output moment of inertia (kg·cm²)": "输出端转动惯量 (kg·cm²)",
        "output torque (nm)": "输出扭矩 (Nm)",
        "peak output torque (nm)": "峰值输出扭矩 (Nm)",
        "peak phase current (a)": "峰值相电流 (A)",
        "peak speed (rpm)": "峰值转速 (rpm)",
        "peak torque (nm)": "峰值扭矩 (Nm)",
        "pitch circle diameter (mm)": "节圆直径 (mm)",
        "pole pairs": "极对数",
        "positioning accuracy (mm)": "定位精度 (mm)",
        "power density (w/kg)": "功率密度 (W/kg)",
        "power supply voltage (v)": "电源电压 (V)",
        "power tube max rotation angle (°)": "动力管最大旋转角度 (°)",
        "precision grade": "精度等级",
        "protection class": "防护等级",
        "rated input speed (r/min)": "额定输入转速 (r/min)",
        "rated input speed (rpm)": "额定输入转速 (rpm)",
        "rated input torque (nm)": "额定输入扭矩 (Nm)",
        "rated load (kg)": "额定负载 (kg)",
        "rated output torque (nm)": "额定输出扭矩 (Nm)",
        "rated phase current (a)": "额定相电流 (A)",
        "rated power (kw)": "额定功率 (kW)",
        "rated power (w)": "额定功率 (W)",
        "rated speed (rpm)": "额定转速 (rpm)",
        "rated torque (nm)": "额定扭矩 (Nm)",
        "rated torque at 2000 rpm (nm)": "2000 rpm 时额定扭矩 (Nm)",
        "rated travel speed (m/s)": "额定行驶速度 (m/s)",
        "rated voltage": "额定电压",
        "rated voltage (v)": "额定电压 (V)",
        "ratio": "速比",
        "ratio i": "速比 i",
        "recommended motor (kw)": "推荐电机功率 (kW)",
        "recommended temperature range (°c)": "推荐温度范围 (°C)",
        "reduction ratio": "减速比",
        "reduction ratio (:1)": "减速比 (:1)",
        "repeatability (±arc min)": "重复定位精度 (±arcmin)",
        "repeatability (±arcmin)": "重复定位精度 (±arcmin)",
        "repeatability (arcsec)": "重复定位精度 (arcsec)",
        "repeatability (mm)": "重复定位精度 (mm)",
        "rigidity (kgf/µm)": "刚度 (kgf/µm)",
        "roller radial static load (n)": "滚柱径向静载荷 (N)",
        "rotational inertia (kg·cm²)": "转动惯量 (kg·cm²)",
        "screw diameter (mm)": "丝杠直径 (mm)",
        "screw dynamic load rating (kn)": "丝杠动载荷额定值 (kN)",
        "screw input torque at max thrust (nm)": "最大推力时丝杠输入扭矩 (Nm)",
        "screw lead (mm)": "丝杠导程 (mm)",
        "screw outer diameter (mm)": "丝杠外径 (mm)",
        "service life (cycles)": "使用寿命(次)",
        "service life (tightening cycles)": "使用寿命(拧紧次数)",
        "service lifetime (h)": "使用寿命 (h)",
        "single wheel load (t)": "单轮负载 (t)",
        "size c1 (mm)": "尺寸 C1 (mm)",
        "size d1 (mm)": "尺寸 D1 (mm)",
        "speed ratio": "速比",
        "stage": "级数",
        "stages": "级数",
        "start torque (mnm)": "启动扭矩 (mNm)",
        "start/stop peak torque (nm)": "启停峰值扭矩 (Nm)",
        "start/stop permissible peak torque (nm)": "启停允许峰值扭矩 (Nm)",
        "static brake torque (nm)": "静态制动扭矩 (Nm)",
        "static load capacity coa (kgf)": "静载荷容量 Coa (kgf)",
        "steering motor rated current (a)": "转向电机额定电流 (A)",
        "steering motor rated power (w)": "转向电机额定功率 (W)",
        "steering motor rated speed (rpm)": "转向电机额定转速 (rpm)",
        "steering motor rated torque (nm)": "转向电机额定扭矩 (Nm)",
        "steering ratio": "转向速比",
        "stroke (mm)": "行程 (mm)",
        "structural form (hf/hs/sf/ss)": "结构形式 (HF/HS/SF/SS)",
        "supply voltage (v)": "供电电压 (V)",
        "tightening speed (rpm)": "拧紧转速 (rpm)",
        "torque constant (nm/a)": "扭矩常数 (Nm/A)",
        "torsional rigidity (nm/arcmin)": "扭转刚度 (Nm/arcmin)",
        "total weight (kg)": "总重量 (kg)",
        "transmission accuracy (arc min)": "传动精度 (arcmin)",
        "transmission accuracy (arcmin)": "传动精度 (arcmin)",
        "turning radius (mm)": "转弯半径 (mm)",
        "variant": "型式",
        "variant (fl/fr/fh/fc or l/r/h/c)": "型式 (FL/FR/FH/FC 或 L/R/H/C)",
        "variant (hp = low backlash, ht = high torque)": "型式 (HP = 低背隙,HT = 高扭矩)",
        "variant (reducer / module)": "型式(减速器 / 模组)",
        "variant (standard/precision)": "型式(标准 / 精密)",
        "variant / model code": "型式 / 型号代码",
        "voltage (v dc)": "电压 (V DC)",
        "voltage (v)": "电压 (V)",
        "walking motor rated current (a)": "行走电机额定电流 (A)",
        "walking motor rated power (w)": "行走电机额定功率 (W)",
        "walking motor rated speed (rpm)": "行走电机额定转速 (rpm)",
        "walking motor rated torque (nm)": "行走电机额定扭矩 (Nm)",
        "weight (g)": "重量 (g)",
        "weight (kg)": "重量 (kg)",
        "weight per 100 mm stroke (kg)": "每 100mm 行程重量 (kg)",
        "wheel diameter (mm)": "车轮直径 (mm)",
        "wheel width (mm)": "车轮宽度 (mm)",
        "with brake": "带制动器",
    },
}

# ---------------------------------------------------------------------
# Product-family display names (ProductType.name).  Exact-match keyed on
# the canonical English; model codes in parentheses stay untranslated.
# ---------------------------------------------------------------------
_FAMILY_NAMES: dict[str, dict[str, str]] = {
    "ZH": {
        "AGV drive wheel (KFQ150)": "AGV 驱动轮 (KFQ150)",
        "AGV steering & differential wheel": "AGV 转向 & 差速轮",
        "Belt-conveyor planetary drive (PWJY)": "皮带输送机行星驱动 (PWJY)",
        "Compact harmonic gear (8/11)": "紧凑型谐波减速器 (8/11)",
        "Compact harmonic gear (KBD-MC)": "紧凑型谐波减速器 (KBD-MC)",
        "Compact harmonic gear (KCD-MC)": "紧凑型谐波减速器 (KCD-MC)",
        "Compact harmonic gear (KSB/KSBG-MO)": "紧凑型谐波减速器 (KSB/KSBG-MO)",
        "Component harmonic gear set (KB/KBG-MC)": "组件型谐波减速器组 (KB/KBG-MC)",
        "Component harmonic gear set (KC/KCG-MC)": "组件型谐波减速器组 (KC/KCG-MC)",
        "Direct-drive electric cylinder (KFDG)": "直驱电动缸 (KFDG)",
        "Folded electric cylinder": "折返式电动缸",
        "General-purpose planetary gearbox (R)": "通用行星减速机 (R)",
        "Hand-crank planetary gearbox (KPX-S)": "手摇行星减速机 (KPX-S)",
        "Hand-input planetary gearbox (KPX-SY)": "手动输入行星减速机 (KPX-SY)",
        "Hat-type compact harmonic gear (KSB/KSBG-HO)": "礼帽型紧凑谐波减速器 (KSB/KSBG-HO)",
        "Hat-type harmonic gear (KB/KBG-HO)": "礼帽型谐波减速器 (KB/KBG-HO)",
        "High-precision planetary gearbox (5KH)": "高精度行星减速机 (5KH)",
        "High-precision planetary gearbox (KH)": "高精度行星减速机 (KH)",
        "High-voltage servo motor (XAM)": "高压伺服电机 (XAM)",
        "Hollow-shaft harmonic gear (KB/KBG-HF)": "中空轴谐波减速器 (KB/KBG-HF)",
        "Integrated servo drive wheel (XGV)": "一体化伺服驱动轮 (XGV)",
        "Micro planetary gearbox (W)": "微型行星减速机 (W)",
        "Multi-axis servo drive (RD)": "多轴伺服驱动器 (RD)",
        "Planetary roller screw": "行星滚柱丝杠",
        "Precision ball screw": "精密滚珠丝杠",
        "Precision planetary gearbox (FL070)": "精密行星减速机 (FL070)",
        "Precision planetary gearbox (F-series)": "精密行星减速机 (F 系列)",
        "Precision planetary gearbox (K-series)": "精密行星减速机 (K 系列)",
        "Precision planetary gearbox (S-series)": "精密行星减速机 (S 系列)",
        "Right-angle disc planetary (KVH)": "直角盘式行星减速机 (KVH)",
        "Right-angle hypoid gearbox (KGR)": "直角准双曲面减速机 (KGR)",
        "Right-angle hypoid gearbox (K-R)": "直角准双曲面减速机 (K-R)",
        "Robot joint reducer (KR)": "机器人关节减速器 (KR)",
        "Servo linear joint module": "伺服直线关节模组",
        "Servo planetary joint module": "伺服行星关节模组",
        "Slewing planetary drive (PWHZ)": "回转行星驱动 (PWHZ)",
        "Spiral-bevel gearbox (KTFR1)": "螺旋锥齿轮减速机 (KTFR1)",
        "Spiral-bevel gearbox (KT-series)": "螺旋锥齿轮减速机 (KT 系列)",
        "Standard harmonic gear (KB/KBG-SO)": "标准谐波减速器 (KB/KBG-SO)",
        "Tightening tool gearbox (PL)": "拧紧工具减速机 (PL)",
        "Tightening tool gearbox (TK)": "拧紧工具减速机 (TK)",
        "Tightening tool gearbox (TKZ)": "拧紧工具减速机 (TKZ)",
        "Tightening tool gearbox (TL)": "拧紧工具减速机 (TL)",
        "Tunneling planetary drive (PWZD)": "掘进行星驱动 (PWZD)",
        "Two-speed planetary gearbox (ZF-S)": "双速行星减速机 (ZF-S)",
        "Wheel-hub planetary drive (PWZQ)": "轮毂行星驱动 (PWZQ)",
    },
}

# ---------------------------------------------------------------------
# Broader family-group names (ProductType.family).
# ---------------------------------------------------------------------
_FAMILY_GROUPS: dict[str, dict[str, str]] = {
    "ZH": {
        "AGV / AMR Drive Solution": "AGV / AMR 驱动方案",
        "Planetary Roller Screw": "行星滚柱丝杠",
        "Precision Planetary Gearbox": "精密行星减速机",
        "RV / Robot Reducer": "RV / 机器人减速器",
        "Servo Motor Solution": "伺服电机方案",
        "Spiral Bevel Gearbox": "螺旋锥齿轮减速机",
        "Strain Wave / Harmonic Gear": "谐波减速器",
    },
}


def tr_label(label: str | None, lang: str | None) -> str:
    """Localize a ``spec_schema`` field label; fall back to English."""
    if not label:
        return label or ""
    code = _norm(lang)
    if code == DEFAULT_LANGUAGE:
        return label
    table = _LABELS.get(code)
    if not table:
        return label
    return table.get(label.strip().lower(), label)


def tr_family_name(name: str | None, lang: str | None) -> str:
    """Localize a product-family display name; fall back to English."""
    if not name:
        return name or ""
    code = _norm(lang)
    if code == DEFAULT_LANGUAGE:
        return name
    table = _FAMILY_NAMES.get(code)
    if not table:
        return name
    return table.get(name, name)


def tr_family_group(name: str | None, lang: str | None) -> str:
    """Localize a family-group name; fall back to English."""
    if not name:
        return name or ""
    code = _norm(lang)
    if code == DEFAULT_LANGUAGE:
        return name
    table = _FAMILY_GROUPS.get(code)
    if not table:
        return name
    return table.get(name, name)
