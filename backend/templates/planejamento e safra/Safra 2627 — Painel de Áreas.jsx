{% extends "base.html" %}

{% block title %}Safra 26/27 — Painel de Áreas{% endblock %}

{% block head_extra %}
<script src="https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@babel/standalone/babel.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prop-types@15.8.1/prop-types.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/recharts@2.12.7/umd/Recharts.min.js"></script>
{% endblock %}

{% block content %}
<div id="safra-2627-root" class="bg-white rounded-lg shadow border border-slate-100 p-6 text-slate-700" data-mounted="0">
    Carregando painel…
</div>
<noscript>
    <div class="mt-4 bg-amber-50 border border-amber-200 text-amber-800 rounded p-3 text-sm">
        JavaScript está desativado no navegador. Ative para usar o painel.
    </div>
</noscript>

<script>
    (function () {
        window.addEventListener("load", function () {
            setTimeout(function () {
                var el = document.getElementById("safra-2627-root");
                if (!el) return;
                if (String(el.dataset.mounted || "0") === "1") return;
                el.innerHTML = "" +
                    "<div style='font-weight:700; color:#1f2937; font-size:18px; margin-bottom:8px;'>Painel não carregou</div>" +
                    "<div style='color:#64748b; font-size:14px;'>As bibliotecas do painel (React/Recharts/XLSX) não carregaram. Verifique a internet ou bloqueio de CDN.</div>" +
                    "<div style='color:#64748b; font-size:13px; margin-top:10px;'>Dica: abra o Console (F12) para ver o erro de carregamento.</div>";
            }, 1500);
        });
    })();
</script>

{% verbatim %}
<script type="text/babel">
  const { useState, useCallback, useEffect } = React;
  const {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, PieChart, Pie, Cell, LabelList,
  } = Recharts;

  const PALETTE = ["#639922","#1D9E75","#378ADD","#D4537E","#BA7517","#533AB7","#D85A30","#888780","#0F6E56","#993556","#3B6D11"];

  const INTERNAL_FIELDS_DEFAULT = [
    { key:"vendedor",        label:"Agrônomo",        required:true,  aliases:["agronomo","agrônomo","vendedor","rotulos_de_linha","nome_vendedor","seller"] },
    { key:"safra",           label:"Safra",          required:false, aliases:["safra","safra_2627","safra_26_27","safra 26/27","safra 2627"] },
    { key:"cod_empresa",     label:"Cód. Empresa",    required:false, aliases:["cod_empresa","codigo_empresa","empresa"] },
    { key:"nome_associado",  label:"Associado",       required:true,  aliases:["nome_associado","associado","produtor","cliente"] },
    { key:"cod_imovel",      label:"Cód. Imóvel",     required:false, aliases:["cod_imovel","codigo_imovel"] },
    { key:"nome_imovel",     label:"Imóvel / Fazenda",required:true,  aliases:["nome_imovel","imovel","fazenda","propriedade"] },
    { key:"nome_gleba",      label:"Gleba / Talhão",  required:true,  aliases:["nome_gleba","gleba","talhao","talhão"] },
    { key:"area_cultivavel", label:"Área Cultivável", required:true,  aliases:["area_cultivavel","area cultivavel","hectares","ha","area","soma de area_cultivavel"] },
    { key:"area_planejada",  label:"Área Planejada",  required:false, aliases:["area_planejada","area planejada","soma de area planejada"] },
  ];

  const fmt = (n, dec=2) => Number(n||0).toLocaleString("pt-BR",{minimumFractionDigits:dec,maximumFractionDigits:dec});

  function autoMatch(col, field) {
    const n = s => String(s).toLowerCase().replace(/[\s_\-\.]/g,"");
    return field.aliases.some(a => n(a) === n(col));
  }

  function buildAutoMap(cols, fields) {
    const map = {};
    (fields || []).forEach(f => { map[f.key] = cols.find(c => autoMatch(c,f)) || ""; });
    return map;
  }

  function forwardFill(rows, keys) {
    const last = {};
    return rows.map(row => {
      const out = {...row};
      keys.forEach(k => {
        const empty = out[k]==null || String(out[k]).trim()==="";
        if (empty) { if (last[k]!=null) out[k]=last[k]; } else last[k]=out[k];
      });
      return out;
    });
  }

  function XlsxImporter({ onImport, onClose, internalFields = INTERNAL_FIELDS_DEFAULT }) {
    const [step,      setStep]      = useState("upload");
    const [workbook,  setWorkbook]  = useState(null);
    const [fileName,  setFileName]  = useState("");
    const [selSheet,  setSelSheet]  = useState("");
    const [excelCols, setExcelCols] = useState([]);
    const [allRows,   setAllRows]   = useState([]);
    const [headerRow, setHeaderRow] = useState(0);
    const [colMap,    setColMap]    = useState({});
    const [extraSel,  setExtraSel]  = useState([]);
    const [ffFields,  setFfFields]  = useState(["vendedor","cod_empresa","nome_associado","cod_imovel","nome_imovel"]);
    const [preview,   setPreview]   = useState([]);
    const [extraKeys, setExtraKeys] = useState([]);
    const [drag,      setDrag]      = useState(false);
    const [err,       setErr]       = useState("");

    const readFile = file => {
      if (!file?.name.match(/\.xlsx?$/i)) return setErr("Use um arquivo .xlsx ou .xls");
      setFileName(file.name); setErr("");
      const reader = new FileReader();
      reader.onload = e => {
        try {
          const wb = XLSX.read(new Uint8Array(e.target.result), {type:"array"});
          setWorkbook(wb);
          const auto = wb.SheetNames.find(s=>/dinamica/i.test(s)) || wb.SheetNames[0];
          setSelSheet(auto);
          setStep("sheet");
        } catch(ex) { setErr("Erro ao ler arquivo: "+ex.message); }
      };
      reader.readAsArrayBuffer(file);
    };

    const confirmSheet = () => {
      try {
        const ws   = workbook.Sheets[selSheet];
        const raw  = XLSX.utils.sheet_to_json(ws,{header:1,defval:""});
        const hIdx = raw.findIndex(r=>r.some(c=>String(c).trim()!==""));
        setHeaderRow(hIdx<0?0:hIdx);
        setAllRows(raw);
        const cols = (raw[hIdx<0?0:hIdx]||[]).map(String).filter(c=>c.trim()!=="");
        setExcelCols(cols);
        setColMap(buildAutoMap(cols, internalFields));
        setExtraSel([]);
        setStep("map");
      } catch(ex) { setErr("Erro ao ler aba: "+ex.message); }
    };

    const mappedExcelCols = new Set(Object.values(colMap).filter(Boolean));
    const unmappedCols    = excelCols.filter(c => !mappedExcelCols.has(c));

    const confirmMap = () => {
      try {
        const headers = allRows[headerRow].map(String);
        let objects = allRows.slice(headerRow+1)
          .filter(r=>r.some(c=>c!==""&&c!=null))
          .map(row => { const o={}; headers.forEach((h,i)=>{o[h]=row[i]??""}); return o; });

        const ffCols = ffFields.map(k=>colMap[k]).filter(Boolean);
        objects = forwardFill(objects, ffCols);

        const normalized = objects.map(obj => {
          const rec = {};
          internalFields.forEach(f => {
            const col = colMap[f.key];
            rec[f.key] = col ? (obj[col]??null) : null;
          });
          rec.area_cultivavel = parseFloat(rec.area_cultivavel)||0;
          rec.area_planejada  = parseFloat(rec.area_planejada)||0;
          if (rec.cod_empresa) rec.cod_empresa = String(rec.cod_empresa).split(".")[0].trim();
          if (rec.cod_imovel)  rec.cod_imovel  = String(rec.cod_imovel).split(".")[0].trim();
          if (rec.nome_gleba)  rec.nome_gleba  = String(rec.nome_gleba).trim();
          rec._unit = rec.banco ?? rec.unidade ?? rec.nome_unidade ?? rec.cod_empresa ?? "";
          extraSel.forEach(col => { rec["extra:"+col] = obj[col]??""; });
          return rec;
        }).filter(r=>r.area_cultivavel>0||(r.nome_gleba&&r.nome_gleba!=="null"));

        setPreview(normalized);
        setExtraKeys(extraSel.map(c=>"extra:"+c));
        setStep("preview");
      } catch(ex) { setErr("Erro ao processar: "+ex.message); }
    };

    const requiredOk = internalFields.filter(f=>f.required).every(f=>colMap[f.key]);
    const steps = ["upload","sheet","map","preview"];
    const stepLabels = ["1. Arquivo","2. Aba","3. Colunas","4. Confirmar"];
    const vendLabel = internalFields.find(f=>f.key==="vendedor")?.label || "Agrônomo";
    const vendPluralLower =
      vendLabel === "Agrônomo" ? "agrônomos"
      : vendLabel === "Vendedor" ? "vendedores"
      : ((vendLabel.endsWith("s") ? vendLabel : (vendLabel + "s")).toLowerCase());

    const toggleExtra = col => setExtraSel(p => p.includes(col) ? p.filter(c=>c!==col) : [...p,col]);

    return (
      <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.5)",display:"flex",
        alignItems:"center",justifyContent:"center",zIndex:9999,padding:16}}>
        <div style={{background:"#fff",borderRadius:16,width:"100%",maxWidth:600,
          maxHeight:"92vh",overflowY:"auto",boxShadow:"0 24px 64px rgba(0,0,0,.25)"}}>

          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
            padding:"16px 20px",borderBottom:"1px solid #edf2e4"}}>
            <div>
              <h2 style={{fontSize:16,fontWeight:700,margin:0,color:"#1a1a1a"}}>📂 Importar arquivo .xlsx</h2>
              {fileName && <p style={{fontSize:11,color:"#888",margin:"2px 0 0"}}>{fileName}</p>}
            </div>
            <button onClick={onClose} style={{background:"#f5f5f5",border:"none",borderRadius:"50%",
              width:32,height:32,cursor:"pointer",fontSize:16,color:"#555",display:"flex",
              alignItems:"center",justifyContent:"center"}}>✕</button>
          </div>

          <div style={{display:"flex",padding:"10px 20px",borderBottom:"1px solid #f0f5e8",gap:2}}>
            {steps.map((s,i)=>{
              const ci=steps.indexOf(step), mi=i, done=mi<ci, active=mi===ci;
              return (
                <div key={s} style={{display:"flex",alignItems:"center",flex:1,gap:4}}>
                  <span style={{width:22,height:22,borderRadius:"50%",fontSize:11,fontWeight:700,flexShrink:0,
                    display:"flex",alignItems:"center",justifyContent:"center",
                    background:done?"#639922":active?"#eaf3de":"#f0f0f0",
                    color:done?"#fff":active?"#3b6d11":"#bbb"}}>{done?"✓":i+1}</span>
                  <span style={{fontSize:11,color:active?"#3b6d11":"#bbb",fontWeight:active?600:400,whiteSpace:"nowrap"}}>
                    {stepLabels[i]}
                  </span>
                  {i<3 && <span style={{color:"#ddd",marginLeft:"auto",fontSize:12}}>›</span>}
                </div>
              );
            })}
          </div>

          <div style={{padding:20}}>
            {err && <div style={{background:"#fff0f0",border:"1px solid #fcc",borderRadius:8,
              padding:"10px 14px",fontSize:13,color:"#c00",marginBottom:14}}>⚠️ {err}</div>}

            {step==="upload" && (
              <label onDragOver={e=>{e.preventDefault();setDrag(true)}}
                onDragLeave={()=>setDrag(false)}
                onDrop={e=>{e.preventDefault();setDrag(false);readFile(e.dataTransfer.files[0])}}
                style={{display:"block",border:`2px dashed ${drag?"#639922":"#c5d9a0"}`,borderRadius:12,
                  padding:"44px 24px",textAlign:"center",cursor:"pointer",
                  background:drag?"#f2fae6":"#fafdf5",transition:"all .15s"}}>
                <div style={{fontSize:48,marginBottom:12}}>📊</div>
                <p style={{fontWeight:700,color:"#3b6d11",fontSize:15,margin:"0 0 6px"}}>
                  Clique ou arraste seu arquivo aqui
                </p>
                <p style={{color:"#aaa",fontSize:12,margin:"0 0 14px"}}>Suporta .xlsx e .xls</p>
                <input type="file" accept=".xlsx,.xls" style={{fontSize:13,color:"#555"}}
                  onChange={e=>readFile(e.target.files[0])}/>
              </label>
            )}

            {step==="sheet" && (
              <div>
                <p style={{fontSize:13,color:"#555",marginBottom:14}}>Selecione a aba com os dados:</p>
                <div style={{display:"flex",flexDirection:"column",gap:8,marginBottom:20}}>
                  {workbook?.SheetNames.map(s=>(
                    <label key={s} style={{display:"flex",alignItems:"center",gap:10,padding:"10px 14px",
                      border:`.5px solid ${selSheet===s?"#639922":"#e0e0e0"}`,borderRadius:8,
                      cursor:"pointer",background:selSheet===s?"#f2fae6":"#fff"}}>
                      <input type="radio" name="sheet" checked={selSheet===s}
                        onChange={()=>setSelSheet(s)} style={{accentColor:"#639922"}}/>
                      <span style={{fontWeight:selSheet===s?700:400,fontSize:13}}>📋 {s}</span>
                      {selSheet===s && <span style={{marginLeft:"auto",fontSize:11,color:"#639922",fontWeight:600}}>✓ selecionada</span>}
                    </label>
                  ))}
                </div>
                <div style={{display:"flex",gap:8,justifyContent:"flex-end"}}>
                  <button onClick={()=>setStep("upload")} style={btnSec}>← Voltar</button>
                  <button onClick={confirmSheet} style={btnPri}>Continuar →</button>
                </div>
              </div>
            )}

            {step==="map" && (
              <div>
                <p style={{fontSize:13,color:"#555",marginBottom:4}}>
                  Relacione as colunas do arquivo com os campos do dashboard.
                </p>
                <p style={{fontSize:11,color:"#888",marginBottom:14}}>
                  ✨ Auto-detectamos as colunas. Ajuste se necessário.
                </p>

                <div style={{display:"flex",flexDirection:"column",gap:6,marginBottom:16}}>
                  {internalFields.map(f=>{
                    const ok=!!colMap[f.key];
                    return (
                      <div key={f.key} style={{display:"grid",gridTemplateColumns:"1fr 1fr",
                        alignItems:"center",gap:10,padding:"8px 12px",borderRadius:8,
                        background:ok?"#f8fdf2":f.required?"#fff8f5":"#fafafa",
                        border:`.5px solid ${ok?"#c5d9a0":f.required?"#f0c4b0":"#e8e8e8"}`}}>
                        <div style={{fontSize:12,fontWeight:500,color:"#333"}}>
                          {f.label}
                          {f.required && <span style={{color:"#c00",marginLeft:3}}>*</span>}
                          {ok && <span style={{marginLeft:6,color:"#639922",fontSize:11}}>✓</span>}
                        </div>
                        <select value={colMap[f.key]||""} onChange={e=>setColMap(p=>({...p,[f.key]:e.target.value}))}
                          style={{fontSize:12,padding:"5px 8px",border:".5px solid #ccc",borderRadius:6,background:"#fff",width:"100%"}}>
                          <option value="">— não mapear —</option>
                          {excelCols.map(c=><option key={c} value={c}>{c}</option>)}
                        </select>
                      </div>
                    );
                  })}
                </div>

                {unmappedCols.length > 0 && (
                  <div style={{background:"#f0f5fb",border:".5px solid #c0d4f0",borderRadius:10,
                    padding:"12px 14px",marginBottom:16}}>
                    <p style={{fontSize:12,fontWeight:700,color:"#2660b8",margin:"0 0 4px"}}>
                      ✦ {unmappedCols.length} coluna{unmappedCols.length>1?"s":""} extra{unmappedCols.length>1?"s":""} detectada{unmappedCols.length>1?"s":""}
                    </p>
                    <p style={{fontSize:11,color:"#668",margin:"0 0 10px"}}>
                      Selecione as que deseja incluir na tabela e no export. Você pode incluir todas.
                    </p>
                    <div style={{display:"flex",gap:6,marginBottom:10,flexWrap:"wrap"}}>
                      <button onClick={()=>setExtraSel(unmappedCols)}
                        style={{fontSize:11,padding:"3px 10px",border:".5px solid #c0d4f0",borderRadius:6,
                          background:"#2660b8",color:"#fff",cursor:"pointer"}}>
                        ✓ Selecionar todas
                      </button>
                      <button onClick={()=>setExtraSel([])}
                        style={{fontSize:11,padding:"3px 10px",border:".5px solid #c0d4f0",borderRadius:6,
                          background:"#fff",color:"#555",cursor:"pointer"}}>
                        ✗ Limpar
                      </button>
                    </div>
                    <div style={{display:"flex",flexWrap:"wrap",gap:6}}>
                      {unmappedCols.map(col=>{
                        const sel = extraSel.includes(col);
                        return (
                          <label key={col} style={{display:"flex",alignItems:"center",gap:6,
                            padding:"5px 10px",borderRadius:20,cursor:"pointer",fontSize:12,
                            border:`.5px solid ${sel?"#2660b8":"#c0d4f0"}`,
                            background:sel?"#ddeaff":"#fff",color:sel?"#2660b8":"#555",
                            fontWeight:sel?600:400,transition:"all .12s"}}>
                            <input type="checkbox" checked={sel} onChange={()=>toggleExtra(col)}
                              style={{accentColor:"#2660b8",margin:0}}/>
                            {col}
                          </label>
                        );
                      })}
                    </div>
                    {extraSel.length>0 && (
                      <p style={{fontSize:11,color:"#2660b8",margin:"8px 0 0",fontWeight:500}}>
                        ✓ {extraSel.length} coluna{extraSel.length>1?"s":""} selecionada{extraSel.length>1?"s":""}
                      </p>
                    )}
                  </div>
                )}

                <div style={{background:"#f5f9ee",borderRadius:8,padding:"10px 14px",marginBottom:16}}>
                  <p style={{fontSize:12,fontWeight:600,color:"#3b6d11",margin:"0 0 4px"}}>
                    🔁 Forward-fill (preencher células em branco)
                  </p>
                  <p style={{fontSize:11,color:"#888",margin:"0 0 10px"}}>
                    Ative nos campos que repetem valores nas linhas abaixo (tabelas dinâmicas).
                  </p>
                  <div style={{display:"flex",flexWrap:"wrap",gap:10}}>
                    {internalFields.filter(f=>!f.key.startsWith("area")).map(f=>(
                      <label key={f.key} style={{display:"flex",alignItems:"center",gap:5,fontSize:12,cursor:"pointer"}}>
                        <input type="checkbox" checked={ffFields.includes(f.key)}
                          onChange={e=>setFfFields(p=>e.target.checked?[...p,f.key]:p.filter(k=>k!==f.key))}
                          style={{accentColor:"#639922"}}/>
                        {f.label}
                      </label>
                    ))}
                  </div>
                </div>

                {!requiredOk && <p style={{fontSize:12,color:"#e67e22",marginBottom:12}}>
                  ⚠️ Mapeie todos os campos obrigatórios (*) para continuar.
                </p>}
                <div style={{display:"flex",gap:8,justifyContent:"flex-end"}}>
                  <button onClick={()=>setStep("sheet")} style={btnSec}>← Voltar</button>
                  <button onClick={confirmMap} disabled={!requiredOk}
                    style={{...btnPri,opacity:requiredOk?1:.5}}>Processar →</button>
                </div>
              </div>
            )}

            {step==="preview" && (
              <div>
                <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:8,marginBottom:16}}>
                  {[
                    ["📊",preview.length,"registros"],
                    ["👤",[...new Set(preview.map(r=>r.vendedor))].length,vendPluralLower],
                    ["🏠",[...new Set(preview.map(r=>r.nome_imovel))].length,"imóveis"],
                    ["📐",fmt(preview.reduce((s,r)=>s+r.area_cultivavel,0),0),"ha total"],
                  ].map(([icon,val,label])=>(
                    <div key={label} style={{background:"#f5f9ee",borderRadius:8,padding:10,textAlign:"center"}}>
                      <div style={{fontSize:20}}>{icon}</div>
                      <div style={{fontWeight:700,fontSize:15,color:"#1a1a1a"}}>{val}</div>
                      <div style={{fontSize:10,color:"#888"}}>{label}</div>
                    </div>
                  ))}
                </div>
                {extraKeys.length>0 && (
                  <div style={{background:"#f0f5fb",borderRadius:8,padding:"8px 12px",marginBottom:12,fontSize:12,color:"#2660b8"}}>
                    ✦ {extraKeys.length} coluna{extraKeys.length>1?"s":""} extra incluída{extraKeys.length>1?"s":""}: {extraSel.join(", ")}
                  </div>
                )}
                <p style={{fontSize:12,color:"#888",marginBottom:8}}>Prévia das primeiras linhas:</p>
                <div style={{overflowX:"auto",borderRadius:8,border:".5px solid #e0e8d4",marginBottom:4}}>
                  <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                    <thead>
                      <tr style={{background:"#f0f5e8"}}>
                        {[
                          (internalFields.find(f=>f.key==="vendedor")?.label || "Agrônomo"),
                          "Associado","Imóvel","Gleba","Área (ha)",...extraSel
                        ].map(h=>(
                          <th key={h} style={{padding:"7px 10px",fontWeight:500,color:"#555",textAlign:"left",whiteSpace:"nowrap"}}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.slice(0,8).map((r,i)=>(
                        <tr key={i} style={{borderTop:".5px solid #edf2e4"}}>
                          <td style={{padding:"5px 10px",color:"#333"}}>{r.vendedor}</td>
                          <td style={{padding:"5px 10px",color:"#555"}}>{r.nome_associado}</td>
                          <td style={{padding:"5px 10px",color:"#555"}}>{r.nome_imovel}</td>
                          <td style={{padding:"5px 10px",color:"#555"}}>{r.nome_gleba}</td>
                          <td style={{padding:"5px 10px",color:"#3b6d11",fontWeight:600}}>{fmt(r.area_cultivavel)}</td>
                          {extraSel.map(col=>(
                            <td key={col} style={{padding:"5px 10px",color:"#2660b8"}}>{r["extra:"+col]}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {preview.length>8 && <p style={{fontSize:11,color:"#aaa",textAlign:"center",margin:"4px 0 16px"}}>
                  … e mais {preview.length-8} registros
                </p>}
                <div style={{display:"flex",gap:8,justifyContent:"flex-end",marginTop:12}}>
                  <button onClick={()=>setStep("map")} style={btnSec}>← Ajustar</button>
                  <button onClick={()=>onImport(preview, extraKeys, extraSel)} style={btnPri}>
                    ✅ Importar {preview.length} registros
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  function KPI({ label, value, unit, color, sub }) {
    return (
      <div style={{background:"#f5f9ee",borderRadius:10,padding:"12px 14px",borderLeft:`3px solid ${color||"#639922"}`}}>
        <div style={{fontSize:11,color:"#888",marginBottom:3}}>{label}</div>
        <div style={{fontSize:21,fontWeight:700,color:"#1a1a1a"}}>
          {value}{unit&&<span style={{fontSize:11,color:"#888",marginLeft:3}}>{unit}</span>}
        </div>
        {sub && <div style={{fontSize:11,color:"#888",marginTop:2}}>{sub}</div>}
      </div>
    );
  }

  function App() {
    const [data,         setData]         = useState([]);
    const [extraKeys,    setExtraKeys]    = useState([]);
    const [extraLabels,  setExtraLabels]  = useState([]);
    const [internalFields, setInternalFields] = useState(INTERNAL_FIELDS_DEFAULT);
    const [fieldMap,     setFieldMap]     = useState({});
    const [loading,      setLoading]      = useState(true);
    const [loadErr,      setLoadErr]      = useState("");
    const [lastUpdated,  setLastUpdated]  = useState(null);
    const [filterUnit,   setFilterUnit]   = useState("");
    const [filterVend,   setFilterVend]   = useState("");
    const [assocQuery,   setAssocQuery]   = useState("");
    const [filterPlan,   setFilterPlan]   = useState("");
    const [sortCol,      setSortCol]      = useState("area_cultivavel");
    const [sortAsc,      setSortAsc]      = useState(false);
    const [page,         setPage]         = useState(0);
    const [showTable,    setShowTable]    = useState(false);
    const PER_PAGE = 50;

    const loadFromApi = useCallback(async () => {
      setLoading(true);
      setLoadErr("");
      try {
        const resp = await fetch("/api/planejamento/viewprogramacao/", { credentials: "same-origin" });
        if (!resp.ok) {
          const txt = await resp.text();
          throw new Error(txt || ("HTTP " + resp.status));
        }
        const payload = await resp.json();
        const cols = (payload.columns || []).map(String);
        let rows = Array.isArray(payload.rows) ? payload.rows : [];

        if (!cols.length && rows.length) {
          cols.push(...Object.keys(rows[0] || {}));
        }

        const apiFieldsRaw = Array.isArray(payload.internal_fields) ? payload.internal_fields : [];
        const apiFields = apiFieldsRaw
          .map(f => ({
            key: String(f?.key || "").trim(),
            label: String(f?.label || "").trim(),
            required: !!f?.required,
            aliases: Array.isArray(f?.aliases) ? f.aliases.map(String) : [],
          }))
          .filter(f => f.key);
        const fields = apiFields.length ? apiFields : INTERNAL_FIELDS_DEFAULT;

        const profile = payload.profile || {};
        const savedMap = profile.mapping && typeof profile.mapping === "object" ? profile.mapping : {};
        const hasSaved = Object.values(savedMap).some(v => String(v || "").trim() !== "");
        const colMap = hasSaved ? savedMap : buildAutoMap(cols, fields);

        const mapped = new Set(Object.values(colMap).filter(Boolean));
        const forcedExtras = Array.isArray(profile.extra_include) ? profile.extra_include.map(String) : [];
        const extras = forcedExtras.length ? forcedExtras.filter(c => cols.includes(c)) : cols.filter(c => c && !mapped.has(c));
        const extraK = extras.map(c => "extra:" + c);

        const ffKeys = Array.isArray(profile.forward_fill) ? profile.forward_fill.map(String) : [];
        const ffCols = ffKeys.map(k => colMap[k]).filter(Boolean);
        if (ffCols.length) {
          rows = forwardFill(rows, ffCols);
        }

        const normalized = rows.map(obj => {
          const rec = {};
          fields.forEach(f => {
            const col = colMap[f.key];
            rec[f.key] = col ? (obj[col] ?? null) : null;
          });
          rec.area_cultivavel = parseFloat(rec.area_cultivavel) || 0;
          rec.area_planejada  = parseFloat(rec.area_planejada) || 0;
          if (rec.cod_empresa) rec.cod_empresa = String(rec.cod_empresa).split(".")[0].trim();
          if (rec.cod_imovel)  rec.cod_imovel  = String(rec.cod_imovel).split(".")[0].trim();
          if (rec.nome_gleba)  rec.nome_gleba  = String(rec.nome_gleba).trim();
          const unitCol =
            (cols.includes("banco") ? "banco" : "")
            || (cols.includes("nome_banco") ? "nome_banco" : "")
            || (cols.includes("unidade") ? "unidade" : "")
            || (cols.includes("nome_unidade") ? "nome_unidade" : "")
            || (cols.includes("cod_empresa") ? "cod_empresa" : "")
            || colMap["cod_empresa"]
            || "";
          rec._unit = unitCol ? (obj[unitCol] ?? "") : (rec.banco ?? rec.unidade ?? rec.nome_unidade ?? rec.cod_empresa ?? "");
          if (rec._unit != null && String(rec._unit).trim() !== "") rec._unit = String(rec._unit).split(".")[0].trim();
          extras.forEach(col => { rec["extra:" + col] = obj[col] ?? ""; });
          return rec;
        }).filter(r => r.area_cultivavel > 0 || (r.nome_gleba && r.nome_gleba !== "null"));

        setData(normalized);
        setExtraLabels(extras);
        setExtraKeys(extraK);
        setInternalFields(fields);
        setFieldMap(colMap || {});
        setPage(0);
        setFilterUnit("");
        setFilterVend("");
        setAssocQuery("");
        setFilterPlan("");
        setShowTable(false);
        setLastUpdated(new Date());
      } catch (e) {
        setLoadErr(String(e?.message || e));
        setData([]);
        setExtraLabels([]);
        setExtraKeys([]);
        setFieldMap({});
      } finally {
        setLoading(false);
      }
    }, []);

    useEffect(() => { loadFromApi(); }, [loadFromApi]);

    const unidades   = [...new Set(data.map(r=>r._unit).filter(Boolean))].sort();
    const vendedores = [...new Set(
      data.filter(r=>!filterUnit||r._unit===filterUnit).map(r=>r.vendedor).filter(Boolean)
    )].sort();
    const colorMap   = Object.fromEntries([...new Set(data.map(r=>r.vendedor).filter(Boolean))].sort().map((v,i)=>[v,PALETTE[i%PALETTE.length]]));
    const unitColorMap = Object.fromEntries(unidades.map((u,i)=>[u,PALETTE[i%PALETTE.length]]));

    const filtered = data.filter(r => {
      if (filterUnit && r._unit !== filterUnit) return false;
      if (filterVend && r.vendedor !== filterVend) return false;
      if (filterPlan === "programado" && (!r.area_planejada || Number(r.area_planejada) === 0)) return false;
      if (filterPlan === "nao_programado" && (r.area_planejada && Number(r.area_planejada) > 0)) return false;
      if (assocQuery) {
        const q = assocQuery.toLowerCase();
        if (!String(r.nome_associado||"").toLowerCase().includes(q)) return false;
      }
      return true;
    });

    const assocOpts = [...new Set(
      data
        .filter(r=>
          (!filterUnit||r._unit===filterUnit)
          && (!filterVend||r.vendedor===filterVend)
          && (filterPlan!== "programado" || (r.area_planejada && Number(r.area_planejada) > 0))
          && (filterPlan!== "nao_programado" || (!r.area_planejada || Number(r.area_planejada) === 0))
        )
        .map(r=>r.nome_associado)
        .filter(Boolean)
    )].sort();

    const totalCult = filtered.reduce((s,r)=>s+(Number(r.area_cultivavel)||0),0);
    const totalPlan = filtered.reduce((s,r)=>s+(Number(r.area_planejada)||0),0);
    const taxaPlan  = totalCult > 0 ? (totalPlan / totalCult) * 100 : 0;

    const openRows  = filtered.filter(r=>!r.area_planejada || Number(r.area_planejada) === 0);
    const openArea  = openRows.reduce((s,r)=>s+(Number(r.area_cultivavel)||0),0);
    const openCount = openRows.length;
    const assocUnique = new Set(filtered.map(r=>r.nome_associado).filter(Boolean)).size;

    const byUnit = Object.values(
      filtered.reduce((acc,r)=>{
        const k = r._unit || "—";
        if(!acc[k]) acc[k] = { name:k, cultivavel:0, planejada:0 };
        acc[k].cultivavel += Number(r.area_cultivavel)||0;
        acc[k].planejada  += Number(r.area_planejada)||0;
        return acc;
      },{})
    ).sort((a,b)=>String(a.name).localeCompare(String(b.name)));

    const rankAgroDist = Object.values(
      filtered.reduce((acc,r)=>{
        const k = r.vendedor || "—";
        if(!acc[k]) acc[k] = { name:k.split(" ")[0], fullName:k, cultivavel:0, planejada_raw:0 };
        acc[k].cultivavel += Number(r.area_cultivavel)||0;
        acc[k].planejada_raw += Number(r.area_planejada)||0;
        return acc;
      },{})
    )
      .filter(x=>x.fullName!=="—")
      .map(x => {
        const cult = Number(x.cultivavel)||0;
        const plan = Math.min(Number(x.planejada_raw)||0, cult);
        const nao  = Math.max(cult - plan, 0);
        const planPct = cult > 0 ? (plan / cult) * 100 : 0;
        const naoPct  = cult > 0 ? (nao / cult) * 100 : 0;
        return { name:x.name, fullName:x.fullName, cultivavel:cult, planejada:plan, nao_planejada:nao, planejada_pct:planPct, nao_pct:naoPct };
      })
      .sort((a,b)=>{
        const key = filterPlan === "nao_programado" ? "nao_planejada" : "planejada";
        return Number(b[key]||0) - Number(a[key]||0);
      });

    const distByUnit = byUnit
      .map(u => {
        const cult = Number(u.cultivavel) || 0;
        const planRaw = Number(u.planejada) || 0;
        const plan = Math.min(planRaw, cult);
        const nao = Math.max(cult - plan, 0);
        const planPct = cult > 0 ? (plan / cult) * 100 : 0;
        const naoPct  = cult > 0 ? (nao / cult) * 100 : 0;
        return {
          name: u.name,
          cultivavel: cult,
          planejada: plan,
          nao_planejada: nao,
          planejada_pct: planPct,
          nao_pct: naoPct,
          gap_abs: nao,
        };
      })
      .sort((a,b)=>b.gap_abs-a.gap_abs);

    const topOpenAssoc = Object.values(
      openRows.reduce((acc,r)=>{
        const k = r.nome_associado || "";
        if(!k) return acc;
        if(!acc[k]) acc[k] = { name:k, aberto:0 };
        acc[k].aberto += Number(r.area_cultivavel)||0;
        return acc;
      },{})
    ).sort((a,b)=>b.aberto-a.aberto).slice(0,10);

    const DistLabel = (pctKey, color) => props => {
      const { x, y, width, height, value, payload } = props;
      const pct = Number(payload?.[pctKey]) || 0;
      const ha  = Number(value) || 0;
      if (ha <= 0 || width <= 0 || height <= 0) return null;
      const txt = `${fmt(ha,0)} ha · ${fmt(pct,1)}%`;
      const small = pct < 6;
      const lx = small ? (x + width + 8) : (x + width / 2);
      const ly = y + height / 2;
      return (
        <text x={lx} y={ly} fill={color} fontSize={11} fontWeight={700}
          textAnchor={small ? "start" : "middle"} dominantBaseline="middle">
          {txt}
        </text>
      );
    };

    const TotalLabel = props => {
      const { x, y, width, height, payload } = props;
      const total = Number(payload?.cultivavel) || 0;
      if (total <= 0 || width <= 0 || height <= 0) return null;
      const lx = x + width + 8;
      const ly = y + height / 2;
      return (
        <text x={lx} y={ly} fill="#888" fontSize={11} fontWeight={600}
          textAnchor="start" dominantBaseline="middle">
          {`${fmt(total,0)} ha total`}
        </text>
      );
    };

    const sortValue = (r, col) => {
      if (col === "unidade") {
        return String(r._unit ?? "");
      }
      if (col === "taxa") {
        const cult = Number(r.area_cultivavel) || 0;
        const plan = Number(r.area_planejada) || 0;
        return cult > 0 ? (plan / cult) * 100 : 0;
      }
      if (col === "status") {
        const open = !r.area_planejada || Number(r.area_planejada) === 0;
        return open ? 0 : 1;
      }
      if (String(col || "").startsWith("extra:")) {
        return String(r[col] ?? "");
      }
      const v = r[col];
      return typeof v === "number" ? v : String(v ?? "");
    };

    const sorted = [...filtered].sort((a,b)=>{
      const av = sortValue(a, sortCol);
      const bv = sortValue(b, sortCol);
      if (typeof av === "number" && typeof bv === "number") return sortAsc ? av - bv : bv - av;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    const totalPages = Math.ceil(sorted.length/PER_PAGE);
    const pageData   = sorted.slice(page*PER_PAGE,(page+1)*PER_PAGE);

    const vendLabel = internalFields.find(f=>f.key==="vendedor")?.label || "Agrônomo";
    const vendPlural =
      vendLabel === "Agrônomo" ? "Agrônomos"
      : vendLabel === "Vendedor" ? "Vendedores"
      : (vendLabel.endsWith("s") ? vendLabel : (vendLabel + "s"));

    const isMapped = k => String(fieldMap?.[k] || "").trim() !== "";
    const TABLE_COLS = [
      { col: "unidade",        label: "Unidade", required: true, derived: true },
      { col: "vendedor",       label: vendLabel, required: true },
      { col: "nome_associado", label: "Associado", required: true },
      { col: "nome_imovel",    label: "Fazenda", required: false },
      { col: "nome_gleba",     label: "Gleba/Talhão", required: false },
      { col: "area_cultivavel",label: "Área Cult. (ha)", required: true },
      { col: "area_planejada", label: "Área Plan. (ha)", required: true },
    ].filter(c => c.derived || !c.required || isMapped(c.col));
    const TABLE_COLS_DERIVED = [
      { col: "taxa", label: "Taxa" },
      { col: "status", label: "Status" },
    ];

    const exportToXlsx = () => {
      const headers = [
        ...TABLE_COLS.map(c => c.label),
        ...TABLE_COLS_DERIVED.map(c => c.label),
        ...extraLabels,
      ];
      const getVal = (r, col) => col === "unidade" ? (r._unit ?? "") : (r[col] ?? "");
      const rows = sorted.map(r => ([
        ...TABLE_COLS.map(c => getVal(r, c.col)),
        ...TABLE_COLS_DERIVED.map(c => (
          c.col === "taxa"
            ? (Number(r.area_cultivavel)||0) > 0 ? ((Number(r.area_planejada)||0)/(Number(r.area_cultivavel)||0))*100 : 0
            : (!r.area_planejada || Number(r.area_planejada)===0) ? "Aberto" : "OK"
        )),
        ...extraKeys.map(k=>r[k]??""),
      ]));
      const ws = XLSX.utils.aoa_to_sheet([headers,...rows]);
      ws["!cols"] = headers.map(() => ({ wch: 18 }));
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Safra 26-27");
      const ts = new Date().toLocaleDateString("pt-BR").replace(/\//g,"-");
      XLSX.writeFile(wb, `Safra_2627_${ts}.xlsx`);
    };

    const exportToCsv = () => {
      const headers = [
        ...TABLE_COLS.map(c => c.label),
        ...TABLE_COLS_DERIVED.map(c => c.label),
        ...extraLabels,
      ];
      const getVal = (r, col) => col === "unidade" ? (r._unit ?? "") : (r[col] ?? "");
      const rows = sorted.map(r => ([
        ...TABLE_COLS.map(c => getVal(r, c.col)),
        ...TABLE_COLS_DERIVED.map(c => (
          c.col === "taxa"
            ? (Number(r.area_cultivavel)||0) > 0 ? ((Number(r.area_planejada)||0)/(Number(r.area_cultivavel)||0))*100 : 0
            : (!r.area_planejada || Number(r.area_planejada)===0) ? "Aberto" : "OK"
        )),
        ...extraKeys.map(k=>r[k]??""),
      ]));
      const esc = v => {
        const s = String(v ?? "");
        if (/[",\r\n;]/.test(s)) return "\"" + s.replace(/"/g, "\"\"") + "\"";
        return s;
      };
      const csv = [headers.map(esc).join(";"), ...rows.map(r=>r.map(esc).join(";"))].join("\r\n");
      const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const ts = new Date().toLocaleDateString("pt-BR").replace(/\//g,"-");
      a.href = url;
      a.download = `Safra_2627_${ts}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    };

    const handleSort = col => {
      if(sortCol===col) setSortAsc(a=>!a);
      else { setSortCol(col); setSortAsc(!(col==="area_cultivavel" || col==="area_planejada" || col==="taxa")); }
      setPage(0);
    };

    const SI = ({col}) => sortCol===col ? (sortAsc?" ▲":" ▼") : <span style={{opacity:.2}}> ⇅</span>;

    const card = {background:"#fff",borderRadius:12,padding:"14px 16px",border:".5px solid #e0e8d4"};
    const ct   = {fontSize:13,fontWeight:600,color:"#555",margin:"0 0 10px"};
    const renderCell = (k, r) => {
      if (k === "unidade") {
        return (
          <td key={k} style={{padding:"7px 10px",color:"#333",whiteSpace:"nowrap"}}>
            {r._unit ?? ""}
          </td>
        );
      }
      if (k === "status") {
        const open = !r.area_planejada || Number(r.area_planejada) === 0;
        return (
          <td key={k} style={{padding:"7px 10px",whiteSpace:"nowrap"}}>
            <span style={{
              display:"inline-block",
              padding:"2px 10px",
              borderRadius:999,
              fontWeight:800,
              fontSize:11,
              background: open ? "#ffe6e6" : "#eaf3de",
              color: open ? "#b00020" : "#3b6d11",
              border: `1px solid ${open ? "#ffb4b4" : "#c5d9a0"}`,
            }}>
              {open ? "Aberto" : "OK"}
            </span>
          </td>
        );
      }
      if (k === "taxa") {
        const cult = Number(r.area_cultivavel) || 0;
        const plan = Number(r.area_planejada) || 0;
        const taxa = cult > 0 ? (plan / cult) * 100 : 0;
        const color = taxa >= 90 ? "#1D9E75" : taxa >= 70 ? "#BA7517" : "#D4537E";
        const bg    = taxa >= 90 ? "#e8fbf1" : taxa >= 70 ? "#fff6e8" : "#ffe9ef";
        return (
          <td key={k} style={{padding:"7px 10px",textAlign:"right",whiteSpace:"nowrap"}}>
            <span style={{background:bg,color:color,padding:"2px 8px",borderRadius:10,fontWeight:800,fontSize:11}}>
              {fmt(taxa,1)}%
            </span>
          </td>
        );
      }
      if (k === "vendedor") {
        return (
          <td key={k} style={{padding:"7px 10px",color:"#333",whiteSpace:"nowrap"}}>
            <span style={{display:"inline-block",width:8,height:8,borderRadius:2,
              background:colorMap[r.vendedor]||PALETTE[0],marginRight:6,verticalAlign:"middle"}}/>
            {r.vendedor}
          </td>
        );
      }
      if (k === "area_cultivavel") {
        return (
          <td key={k} style={{padding:"7px 10px",textAlign:"right",whiteSpace:"nowrap"}}>
            <span style={{background:"#eaf3de",color:"#3b6d11",padding:"2px 8px",
              borderRadius:10,fontWeight:600,fontSize:11}}>{fmt(r.area_cultivavel)}</span>
          </td>
        );
      }
      if (k === "area_planejada") {
        return (
          <td key={k} style={{padding:"7px 10px",textAlign:"right",whiteSpace:"nowrap"}}>
            {(!r.area_planejada||r.area_planejada===0)
              ? <span style={{background:"#fff3e0",color:"#e67e22",padding:"2px 8px",
                  borderRadius:10,fontWeight:700,fontSize:11}}>⚠ 0,00</span>
              : <span style={{background:"#eaf3de",color:"#3b6d11",padding:"2px 8px",
                  borderRadius:10,fontWeight:600,fontSize:11}}>{fmt(r.area_planejada)}</span>}
          </td>
        );
      }
      const v = r[k];
      return (
        <td key={k} style={{padding:"7px 10px",color:"#333",whiteSpace:"nowrap"}}>
          {v ?? ""}
        </td>
      );
    };

    const openTable = () => {
      const preferred =
        (TABLE_COLS.find(c => c.col === "area_planejada") || TABLE_COLS.find(c => c.col === "area_cultivavel") || TABLE_COLS[0] || { col: "area_planejada" }).col;
      setSortCol(preferred);
      setSortAsc(false);
      setPage(0);
      setShowTable(true);
    };

    return (
      <div style={{fontFamily:"system-ui,sans-serif",background:"#f8faf5",minHeight:1024,padding:"clamp(10px, 1.6vw, 18px)",borderRadius:12,width:"100%",boxSizing:"border-box"}}>
        <style>{`
          .kpiGrid { display:grid; gap:8px; margin-bottom:12px; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); }
          .zone3 { display:grid; gap:10px; margin-bottom:12px; grid-template-columns:1fr; }
          .zone4 { display:grid; gap:10px; margin-bottom:12px; grid-template-columns:1fr; }
          @media (min-width: 1100px) {
            .zone3 { grid-template-columns:3fr 2fr; }
            .zone4 { grid-template-columns:1fr 1fr; }
          }
        `}</style>

        <div style={{...card,display:"flex",alignItems:"center",justifyContent:"space-between",
          marginBottom:14,flexWrap:"wrap",gap:10}}>
          <div>
            <h1 style={{fontSize:18,fontWeight:700,color:"#1a1a1a",margin:0}}>🌾 Safra 26/27 — Painel de Áreas</h1>
            <p style={{fontSize:12,color:"#888",margin:"2px 0 0"}}>
              {data.length>0
                ? `${data.length} registros importados${extraLabels.length>0?` · ${extraLabels.length} coluna${extraLabels.length>1?"s":""} extra`:""}`
                : "Nenhum dado carregado"}
            </p>
          </div>
          <button onClick={loadFromApi} disabled={loading} style={{display:"flex",alignItems:"center",gap:8,
            padding:"10px 20px",background:"#639922",color:"#fff",border:"none",borderRadius:10,
            cursor:"pointer",fontSize:14,fontWeight:600,boxShadow:"0 2px 8px rgba(99,153,34,.3)",
            opacity: loading ? .6 : 1}}>
            🔄 {loading ? "Atualizando…" : "Atualizar dados"}
          </button>
        </div>

        {lastUpdated && (
          <div style={{fontSize:12,color:"#888",margin:"-4px 0 12px 0"}}>
            Atualizado em {lastUpdated.toLocaleString("pt-BR")}
          </div>
        )}

        {loadErr && (
          <div style={{background:"#fff5f5",border:"1px solid #ffd1d1",color:"#b00020",
            padding:"10px 14px",borderRadius:10,fontSize:13,marginBottom:12}}>
            Erro ao carregar: {loadErr}
          </div>
        )}

        {data.length===0 && (
          <div style={{...card,textAlign:"center",padding:"60px 24px"}}>
            <div style={{fontSize:56,marginBottom:16}}>📊</div>
            <p style={{fontWeight:700,fontSize:18,color:"#333",marginBottom:8}}>
              {loading ? "Carregando dados…" : "Nenhum dado encontrado"}
            </p>
            <p style={{color:"#888",fontSize:14,marginBottom:24,maxWidth:360,margin:"0 auto 24px"}}>
              Os dados vêm da view capalti.viewprogramacao.
            </p>
            <button onClick={loadFromApi} disabled={loading} style={{padding:"12px 28px",background:"#639922",
              color:"#fff",border:"none",borderRadius:10,cursor:"pointer",fontSize:15,fontWeight:600,
              opacity: loading ? .6 : 1}}>
              🔄 {loading ? "Atualizando…" : "Atualizar dados"}
            </button>
          </div>
        )}

        {data.length>0 && <>
          <div style={{position:"sticky",top:0,zIndex:40,background:"#f8faf5",paddingBottom:12,marginBottom:12}}>
            <div style={card}>
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:10,flexWrap:"wrap"}}>
                <div>
                  <p style={{...ct,margin:0}}>Filtros</p>
                  <span style={{fontSize:11,color:"#888"}}>{filtered.length} registros</span>
                </div>
                <div style={{fontSize:11,color:"#888"}}>
                  {filterUnit ? `Unidade: ${filterUnit}` : "Todas as unidades"}
                  {" · "}
                  {filterVend ? `${vendLabel}: ${filterVend}` : `Todos os ${vendPlural.toLowerCase()}`}
                </div>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:8,marginTop:10}}>
                <div>
                  <div style={{fontSize:11,color:"#64748b",marginBottom:4}}>Unidade</div>
                  <select value={filterUnit} onChange={e=>{setFilterUnit(e.target.value);setFilterVend("");setPage(0);}}
                    style={{width:"100%",fontSize:13,padding:"8px 10px",border:".5px solid #cdd9b8",borderRadius:8,background:"#fff",color:"#333"}}>
                    <option value="">Todas</option>
                    {unidades.map(u=><option key={u} value={u}>{u}</option>)}
                  </select>
                </div>
                <div>
                  <div style={{fontSize:11,color:"#64748b",marginBottom:4}}>{vendLabel}</div>
                  <select value={filterVend} onChange={e=>{setFilterVend(e.target.value);setPage(0);}}
                    style={{width:"100%",fontSize:13,padding:"8px 10px",border:".5px solid #cdd9b8",borderRadius:8,background:"#fff",color:"#333"}}>
                    <option value="">Todos</option>
                    {vendedores.map(v=><option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <div style={{fontSize:11,color:"#64748b",marginBottom:4}}>Associado</div>
                  <input value={assocQuery} onChange={e=>{setAssocQuery(e.target.value);setPage(0);}}
                    list="assoc-list"
                    placeholder="Buscar associado..."
                    style={{width:"100%",fontSize:13,padding:"8px 10px",border:".5px solid #cdd9b8",borderRadius:8,background:"#fff",color:"#333",outline:"none"}}/>
                  <datalist id="assoc-list">
                    {assocOpts.slice(0,200).map(a=><option key={a} value={a}/>)}
                  </datalist>
                </div>
                <div>
                  <div style={{fontSize:11,color:"#64748b",marginBottom:4}}>Planejamento</div>
                  <select value={filterPlan} onChange={e=>{setFilterPlan(e.target.value);setPage(0);}}
                    style={{width:"100%",fontSize:13,padding:"8px 10px",border:".5px solid #cdd9b8",borderRadius:8,background:"#fff",color:"#333"}}>
                    <option value="">Todos</option>
                    <option value="programado">Programado</option>
                    <option value="nao_programado">Não programado</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="kpiGrid">
            <KPI label="Área Cultivável total" value={fmt(totalCult,0)} unit="ha" color="#639922"/>
            <KPI label="Área Planejada total" value={fmt(totalPlan,0)} unit="ha" color="#378ADD"/>
            <KPI
              label="Taxa de Planejamento"
              value={fmt(taxaPlan,1)}
              unit="%"
              color={taxaPlan>=90?"#1D9E75":taxaPlan>=70?"#BA7517":"#D4537E"}
              sub="Planejado / Cultivável"
            />
            <KPI
              label="Área em Aberto"
              value={fmt(openArea,0)}
              unit="ha"
              color="#e67e22"
              sub={`${openCount} registro${openCount!==1?"s":""} sem planejamento`}
            />
            <KPI label="Associados" value={assocUnique} color="#533AB7" sub="únicos"/>
          </div>

          <div className="zone3">
            <div style={card}>
              <p style={ct}>Cultivável vs Planejada por Unidade (ha)</p>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={byUnit} margin={{top:8,right:10,left:0,bottom:0}}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e8f0df"/>
                  <XAxis dataKey="name" tick={{fontSize:11,fill:"#888"}}/>
                  <YAxis tick={{fontSize:11,fill:"#888"}}/>
                  <Tooltip formatter={(v,n)=>[`${fmt(v,0)} ha`, n==="cultivavel"?"Cultivável":"Planejada"]}
                    contentStyle={{fontSize:12,borderRadius:8,border:"1px solid #e0e8d4"}}/>
                  <Bar dataKey="cultivavel" fill="#639922" radius={[4,4,0,0]}/>
                  <Bar dataKey="planejada"  fill="#378ADD" radius={[4,4,0,0]}/>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div style={card}>
              <p style={ct}>{`Ranking de ${vendPlural.toLowerCase()} — Planejada vs Não planejada (ha)`}</p>
              <ResponsiveContainer width="100%" height={Math.min(Math.max(rankAgroDist.length*28+40,220),420)}>
                <BarChart data={rankAgroDist} layout="vertical" margin={{left:8,right:30,top:4,bottom:4}}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e8f0df"/>
                  <XAxis type="number" tick={{fontSize:11,fill:"#888"}} tickFormatter={v=>fmt(v,0)}/>
                  <YAxis type="category" dataKey="name" tick={{fontSize:11,fill:"#555"}} width={90}/>
                  <Tooltip
                    contentStyle={{fontSize:12,borderRadius:8,border:"1px solid #e0e8d4"}}
                    formatter={(v, n, p) => {
                      const d = p?.payload || {};
                      if (n === "planejada") return [`${fmt(v,0)} ha · ${fmt(d.planejada_pct,1)}%`, "Planejada"];
                      if (n === "nao_planejada") return [`${fmt(v,0)} ha · ${fmt(d.nao_pct,1)}%`, "Não planejada"];
                      return [v, n];
                    }}
                    labelFormatter={label => {
                      const row = rankAgroDist.find(x=>x.name===label);
                      if (!row) return label;
                      return `${row.fullName} · ${fmt(row.cultivavel,0)} ha total`;
                    }}
                  />
                  <Bar dataKey="planejada" stackId="a" fill="#1D9E75" radius={[6,0,0,6]}/>
                  <Bar dataKey="nao_planejada" stackId="a" fill="#D4537E" radius={[0,6,6,0]}/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="zone4">
            <div style={card}>
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:10,flexWrap:"wrap"}}>
                <p style={{...ct,margin:0}}>Distribuição de Área por Unidade — Planejada vs Não Planejada</p>
              </div>
              <div style={{fontSize:11,color:"#888",marginTop:6}}>
                ordenado por maior lacuna absoluta ↓
              </div>
              <ResponsiveContainer width="100%" height={Math.min(Math.max(distByUnit.length*44+30,200),420)}>
                <BarChart data={distByUnit} layout="vertical" margin={{left:10,right:90,top:8,bottom:10}} barCategoryGap={12}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e8f0df"/>
                  <XAxis type="number" domain={[0, "dataMax"]} tick={{fontSize:11,fill:"#888"}}
                    tickFormatter={v=>fmt(v,0)}/>
                  <YAxis type="category" dataKey="name" tick={{fontSize:11,fill:"#555"}} width={120}/>
                  <Tooltip
                    contentStyle={{fontSize:12,borderRadius:8,border:"1px solid #e0e8d4"}}
                    formatter={(v, n, p) => {
                      const d = p?.payload || {};
                      if (n === "planejada") return [`${fmt(v,0)} ha · ${fmt(d.planejada_pct,1)}%`, "Planejada"];
                      if (n === "nao_planejada") return [`${fmt(v,0)} ha · ${fmt(d.nao_pct,1)}%`, "Não planejada"];
                      return [v, n];
                    }}
                    labelFormatter={label => {
                      const row = distByUnit.find(x=>x.name===label);
                      if (!row) return label;
                      return `${label} · ${fmt(row.cultivavel,0)} ha total`;
                    }}
                  />
                  <Bar dataKey="planejada" stackId="u" fill="#1D9E75" radius={[6,0,0,6]}>
                  </Bar>
                  <Bar dataKey="nao_planejada" stackId="u" fill="#D4537E" radius={[0,6,6,0]}>
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              </div>
            <div style={card}>
              <p style={ct}>Top 10 associados com maior área em aberto (ha)</p>
              <ResponsiveContainer width="100%" height={Math.min(Math.max(topOpenAssoc.length*30+40,180),340)}>
                <BarChart data={topOpenAssoc} layout="vertical" margin={{left:8,right:40,top:4,bottom:4}}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e8f0df"/>
                  <XAxis type="number" tick={{fontSize:11,fill:"#888"}}/>
                  <YAxis type="category" dataKey="name" tick={{fontSize:11,fill:"#555"}} width={140}/>
                  <Tooltip formatter={(v,_,p)=>[`${fmt(v,0)} ha`,p.payload.name]} contentStyle={{fontSize:12,borderRadius:8}}/>
                  <Bar dataKey="aberto" radius={[0,4,4,0]} fill="#e67e22"
                    label={{position:"right",fontSize:11,fill:"#888",formatter:v=>`${fmt(v,0)}`}}/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div style={{...card,display:"flex",alignItems:"center",justifyContent:"space-between",gap:10,flexWrap:"wrap"}}>
            <div>
              <p style={{...ct,margin:0}}>Tabela completa</p>
              <span style={{fontSize:11,color:"#888"}}>
                {filtered.length} registros · {PER_PAGE} por página
              </span>
            </div>
            <div style={{display:"flex",gap:8,alignItems:"center",flexWrap:"wrap"}}>
              <button onClick={openTable}
                style={{padding:"7px 16px",background:"#2660b8",color:"#fff",border:"none",borderRadius:8,
                  cursor:"pointer",fontSize:13,fontWeight:600,boxShadow:"0 2px 6px rgba(38,96,184,.25)"}}>
                Abrir tabela
              </button>
              <button onClick={exportToCsv}
                style={{padding:"7px 16px",background:"#4b5563",color:"#fff",border:"none",borderRadius:8,
                  cursor:"pointer",fontSize:13,fontWeight:600,boxShadow:"0 2px 6px rgba(75,85,99,.25)"}}>
                Exportar .csv
              </button>
              <button onClick={exportToXlsx}
                style={{padding:"7px 16px",background:"#1d7a3e",color:"#fff",border:"none",borderRadius:8,
                  cursor:"pointer",fontSize:13,fontWeight:600,boxShadow:"0 2px 6px rgba(29,122,62,.25)"}}>
                Exportar .xlsx
              </button>
            </div>
          </div>
        </>}

        {showTable && (
          <div onClick={()=>setShowTable(false)} style={{position:"fixed",inset:0,background:"rgba(0,0,0,.5)",
            display:"flex",alignItems:"center",justifyContent:"center",zIndex:9999,padding:16}}>
            <div onClick={e=>e.stopPropagation()} style={{background:"#fff",borderRadius:16,width:"100%",maxWidth:"min(1100px, 96vw)",
              maxHeight:"92vh",overflow:"hidden",boxShadow:"0 24px 64px rgba(0,0,0,.25)",display:"flex",flexDirection:"column"}}>
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
                padding:"14px 18px",borderBottom:"1px solid #edf2e4",gap:10,flexWrap:"wrap"}}>
                <div>
                  <div style={{fontSize:15,fontWeight:800,color:"#1a1a1a"}}>Tabela completa</div>
                  <div style={{fontSize:11,color:"#888"}}>
                    {filtered.length} registros
                  </div>
                </div>
                <div style={{display:"flex",alignItems:"center",gap:8}}>
                  <button onClick={exportToCsv}
                    style={{display:"flex",alignItems:"center",gap:7,padding:"7px 14px",
                      background:"#4b5563",color:"#fff",border:"none",borderRadius:8,
                      cursor:"pointer",fontSize:13,fontWeight:600,boxShadow:"0 2px 6px rgba(75,85,99,.25)"}}>
                    Exportar .csv
                  </button>
                  <button onClick={exportToXlsx}
                    style={{display:"flex",alignItems:"center",gap:7,padding:"7px 14px",
                      background:"#1d7a3e",color:"#fff",border:"none",borderRadius:8,
                      cursor:"pointer",fontSize:13,fontWeight:600,boxShadow:"0 2px 6px rgba(29,122,62,.25)"}}>
                    Exportar .xlsx
                  </button>
                  <button onClick={()=>setShowTable(false)} style={{background:"#f5f5f5",border:"none",borderRadius:"50%",
                    width:34,height:34,cursor:"pointer",fontSize:16,color:"#555",display:"flex",
                    alignItems:"center",justifyContent:"center"}}>✕</button>
                </div>
              </div>

              <div style={{padding:"12px 14px",overflow:"auto"}}>
                {TABLE_COLS.length === 0 ? (
                  <div style={{background:"#fff8f0",border:"1px solid #ffe0c0",color:"#a85a00",
                    padding:"10px 12px",borderRadius:10,fontSize:13}}>
                    Nenhum campo interno está mapeado para esta origem. Vá em Sistema → Mapeamento de Colunas e faça o vínculo das colunas.
                  </div>
                ) : (
                  <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
                    <thead>
                      <tr style={{background:"#f0f5e8"}}>
                        {TABLE_COLS.map(({col,label})=>(
                          <th key={col} onClick={()=>handleSort(col)} style={{padding:"8px 10px",fontWeight:500,
                            color:"#555",cursor:"pointer",whiteSpace:"nowrap",userSelect:"none",fontSize:12,
                            textAlign:col.startsWith("area")?"right":"left"}}>
                            {label}<SI col={col}/>
                          </th>
                        ))}
                        {TABLE_COLS_DERIVED.map(({col,label})=>(
                          <th key={col} onClick={()=>handleSort(col)} style={{padding:"8px 10px",fontWeight:500,
                            color:"#555",cursor:"pointer",whiteSpace:"nowrap",userSelect:"none",fontSize:12,
                            textAlign:col==="taxa"?"right":"left"}}>
                            {label}<SI col={col}/>
                          </th>
                        ))}
                        {extraLabels.map(label=>(
                          <th key={label} onClick={()=>handleSort("extra:"+label)}
                            style={{padding:"8px 10px",fontWeight:500,color:"#2660b8",cursor:"pointer",
                              whiteSpace:"nowrap",userSelect:"none",fontSize:12,
                              background:"#eef4ff",borderLeft:"2px solid #c0d4f0"}}>
                            ✦ {label}<SI col={"extra:"+label}/>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {pageData.map((r,i)=>{
                        const open = !r.area_planejada || Number(r.area_planejada) === 0;
                        const baseBg = open ? "#fff5f5" : "transparent";
                        const hoverBg = open ? "#ffecec" : "#f8faf5";
                        return (
                          <tr key={i} style={{borderBottom:".5px solid #edf2e4",background:baseBg}}
                            onMouseEnter={e=>e.currentTarget.style.background=hoverBg}
                            onMouseLeave={e=>e.currentTarget.style.background=baseBg}>
                            {TABLE_COLS.map(c => renderCell(c.col, r))}
                            {TABLE_COLS_DERIVED.map(c => renderCell(c.col, r))}
                            {extraKeys.map(k=>(
                              <td key={k} style={{padding:"7px 10px",color:"#2660b8",whiteSpace:"nowrap",
                                background:"#f6f9ff",borderLeft:"2px solid #e8f0ff",fontSize:12}}>
                                {r[k]??""}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>

              {TABLE_COLS.length > 0 && (
                <div style={{display:"flex",alignItems:"center",justifyContent:"flex-end",
                  gap:8,padding:"10px 14px",borderTop:"1px solid #edf2e4",fontSize:12,color:"#888"}}>
                  <span>{page*PER_PAGE+1}–{Math.min((page+1)*PER_PAGE,filtered.length)} de {filtered.length}</span>
                  <button onClick={()=>setPage(p=>p-1)} disabled={page===0}
                    style={{padding:"4px 12px",fontSize:12,cursor:"pointer",borderRadius:6,
                      border:".5px solid #cdd9b8",background:"#f5f9ee",color:"#3b6d11"}}>‹ Anterior</button>
                  <button onClick={()=>setPage(p=>p+1)} disabled={page>=totalPages-1}
                    style={{padding:"4px 12px",fontSize:12,cursor:"pointer",borderRadius:6,
                      border:".5px solid #cdd9b8",background:"#f5f9ee",color:"#3b6d11"}}>Próximo ›</button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  const btnPri = {padding:"9px 20px",fontSize:13,fontWeight:600,cursor:"pointer",borderRadius:8,border:"none",background:"#639922",color:"#fff"};
  const btnSec = {padding:"9px 20px",fontSize:13,cursor:"pointer",borderRadius:8,border:".5px solid #ccc",background:"#fff",color:"#555"};

  const mountEl = document.getElementById("safra-2627-root");
  if (!mountEl) {
    throw new Error("Elemento #safra-2627-root não encontrado.");
  }
  mountEl.dataset.mounted = "1";
  ReactDOM.createRoot(mountEl).render(<App />);
</script>
{% endverbatim %}
{% endblock %}
