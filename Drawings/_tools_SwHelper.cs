using System;
using System.Text;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public static class SwHelper
{
    static ISldWorks App() { return (ISldWorks)Marshal.GetActiveObject("SldWorks.Application"); }

    static ITableAnnotation Bom(IModelDoc2 doc)
    {
        Feature f = (Feature)doc.FirstFeature();
        while (f != null)
        {
            if (f.GetTypeName2() == "BomFeat")
            {
                BomFeature bf = (BomFeature)f.GetSpecificFeature2();
                object[] tas = (object[])bf.GetTableAnnotations();
                return (ITableAnnotation)tas[0];
            }
            f = (Feature)f.GetNextFeature();
        }
        return null;
    }

    public static string DumpBom()
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        ITableAnnotation ta = Bom(doc);
        if (ta == null) return "no BOM";
        StringBuilder sb = new StringBuilder();
        sb.AppendFormat("rows={0} cols={1}\n", ta.RowCount, ta.ColumnCount);
        for (int r = 0; r < ta.RowCount; r++)
        {
            for (int c = 0; c < ta.ColumnCount; c++) { sb.Append(ta.get_Text(r, c)); sb.Append(" | "); }
            sb.Append("\n");
        }
        return sb.ToString();
    }

    // Point a column at a custom property and rename its header; set column widths (m)
    public static string SetupBom(int descCol, string prop, string header, double[] widths)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        ITableAnnotation ta = Bom(doc);
        BomTableAnnotation bta = (BomTableAnnotation)ta;
        bool ok = bta.SetColumnCustomProperty(descCol, prop);
        ta.SetColumnTitle2(descCol, header, true);
        for (int c = 0; c < widths.Length && c < ta.ColumnCount; c++) ta.SetColumnWidth(c, widths[c], 0);
        doc.ForceRebuild3(false);
        return "custom property set=" + ok;
    }

    public static string RebuildBom(string viewName, string template, double x, double y)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        // delete existing BOM features
        Feature f = (Feature)doc.FirstFeature();
        while (f != null)
        {
            Feature next = (Feature)f.GetNextFeature();
            if (f.GetTypeName2() == "BomFeat") { f.Select2(false, 0); doc.Extension.DeleteSelection2(0); }
            f = next;
        }
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = (IView)dd.GetFirstView();
        while (v != null && v.Name != viewName) v = (IView)v.GetNextView();
        if (v == null) return "view not found";
        BomTableAnnotation b = v.InsertBomTable4(false, x, y, (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft,
            (int)swBomType_e.swBomType_PartsOnly, "Default", template, false, (int)swNumberingType_e.swNumberingType_Detailed, false);
        return b == null ? "insert failed" : "inserted";
    }

    // Exclude a component (by Name2) from the BOM in an open assembly
    public static string ExcludeFromBom(string asmPath, string compName)
    {
        ISldWorks app = App();
        IModelDoc2 asm = (IModelDoc2)app.GetOpenDocumentByName(asmPath);
        if (asm == null) return "not open: " + asmPath;
        object[] comps = (object[])((IAssemblyDoc)asm).GetComponents(true);
        int n = 0;
        foreach (object o in comps)
        {
            Component2 c = (Component2)o;
            if (c.Name2 == compName) { c.ExcludeFromBOM = true; n++; }
        }
        return compName + " excluded in " + n + " instance(s)";
    }

    public static string SetPartProp(string path, string name, string value)
    {
        ISldWorks app = App();
        IModelDoc2 d = (IModelDoc2)app.GetOpenDocumentByName(path);
        if (d == null) return "not open";
        CustomPropertyManager cpm = d.Extension.get_CustomPropertyManager("");
        int r = cpm.Add3(name, (int)swCustomInfoType_e.swCustomInfoText, value, (int)swCustomPropertyAddOption_e.swCustomPropertyReplaceValue);
        int e = 0, w = 0;
        bool ok = d.Save3((int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref e, ref w);
        return "add=" + r + " saved=" + ok;
    }

    public static string Layout(string sectionName, string frontName, double sx, double sy, double fx, double fy)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = (IView)dd.GetFirstView(); IView sv = null, fv = null;
        while (v != null) { if (v.Name == sectionName) sv = v; if (v.Name == frontName) fv = v; v = (IView)v.GetNextView(); }
        sv.RemoveAlignment();
        sv.Position = new double[] { sx, sy };
        fv.Position = new double[] { fx, fy };
        doc.ForceRebuild3(false);
        StringBuilder sb = new StringBuilder();
        foreach (IView x in new IView[] { sv, fv })
        {
            double[] o = (double[])x.GetOutline();
            sb.AppendFormat("{0}: ({1:0.000},{2:0.000})-({3:0.000},{4:0.000})\n", x.Name, o[0], o[1], o[2], o[3]);
        }
        return sb.ToString();
    }

    public static string MoveBom(double x, double y)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        ITableAnnotation ta = Bom(doc);
        IAnnotation an = (IAnnotation)ta.GetAnnotation();
        an.SetPosition2(x, y, 0);
        doc.ForceRebuild3(false);
        return BomBox();
    }

    public static string AddNote(string text, double x, double y, double height)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        doc.ClearSelection2(true);
        INote n = (INote)doc.InsertNote(text);
        if (n == null) return "note failed";
        IAnnotation an = (IAnnotation)n.GetAnnotation();
        an.SetPosition2(x, y, 0);
        TextFormat tf = (TextFormat)an.GetTextFormat(0);
        tf.CharHeight = height;
        an.SetTextFormat(0, false, tf);
        return "note ok";
    }

    // Write each part's material name into a text property so a BOM column can show it plainly
    public static string MaterialProps(string topPath)
    {
        ISldWorks app = App();
        IModelDoc2 top = (IModelDoc2)app.GetOpenDocumentByName(topPath);
        object[] comps = (object[])((IAssemblyDoc)top).GetComponents(false);
        var done = new System.Collections.Generic.HashSet<string>();
        int n = 0;
        foreach (object o in comps)
        {
            Component2 c = (Component2)o;
            IModelDoc2 d = (IModelDoc2)c.GetModelDoc2();
            if (d == null || d.GetType() != (int)swDocumentTypes_e.swDocPART) continue;
            string p = d.GetPathName();
            if (!done.Add(p)) continue;
            string db;
            string mat = ((PartDoc)d).GetMaterialPropertyName2("", out db);
            if (string.IsNullOrEmpty(mat)) mat = "-";
            mat = mat.Replace(" hardened 60 HRC", ", 60 HRC");
            CustomPropertyManager cpm = d.Extension.get_CustomPropertyManager("");
            cpm.Add3("MaterialText", (int)swCustomInfoType_e.swCustomInfoText, mat, (int)swCustomPropertyAddOption_e.swCustomPropertyReplaceValue);
            int e = 0, w = 0; d.Save3((int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref e, ref w);
            n++;
        }
        return n + " parts";
    }

    public static string BomTextHeight(double h)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        ITableAnnotation ta = Bom(doc);
        ta.SetTextFormat(false, null);
        TextFormat tf = (TextFormat)ta.GetTextFormat();
        tf.CharHeight = h;
        bool ok = ta.SetTextFormat(false, tf);
        doc.ForceRebuild3(false);
        return "text format set=" + ok;
    }

    public static string BomRowHeight(double h)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        ITableAnnotation ta = Bom(doc);
        for (int r = 0; r < ta.RowCount; r++) ta.SetRowHeight(r, h, 0);
        doc.ForceRebuild3(false);
        return BomBox();
    }

    // fit = "" removes the tolerance
    public static string FitOnDim(string fullNameStart, string fit, bool hole)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = (IView)((IDrawingDoc)doc).GetFirstView();
        while (v != null)
        {
            DisplayDimension d = (DisplayDimension)v.GetFirstDisplayDimension5();
            while (d != null)
            {
                Dimension dm = (Dimension)d.GetDimension2(0);
                if (dm.FullName.StartsWith(fullNameStart))
                {
                    DimensionTolerance t = (DimensionTolerance)dm.Tolerance;
                    if (fit == "") { t.Type = (int)swTolType_e.swTolNONE; return dm.FullName + " tolerance removed"; }
                    t.Type = (int)swTolType_e.swTolFIT;
                    bool ok = hole ? t.SetFitValues(fit, "") : t.SetFitValues("", fit);
                    return dm.FullName + " fit " + fit + " " + ok;
                }
                d = (DisplayDimension)d.GetNext5();
            }
            v = (IView)v.GetNextView();
        }
        return "not found";
    }

    public static string BalloonAt(string viewName, double[] p, double[] tp)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        double[] a = ToSheet(v, p[0] / 1000, p[1] / 1000, p[2] / 1000);
        double[] t = ToSheet(v, tp[0] / 1000, tp[1] / 1000, tp[2] / 1000);
        doc.ClearSelection2(true); dd.ActivateView(viewName);
        if (!doc.Extension.SelectByID2("", "EDGE", a[0], a[1], 0, false, 0, null, 0)) return "select failed";
        BalloonOptions bo = (BalloonOptions)doc.Extension.CreateBalloonOptions();
        bo.Style = (int)swBalloonStyle_e.swBS_Circular;
        bo.Size = (int)swBalloonFit_e.swBF_2Chars;
        bo.UpperTextContent = (int)swBalloonTextContent_e.swBalloonTextItemNumber;
        INote n = (INote)doc.Extension.InsertBOMBalloon2(bo);
        doc.ClearSelection2(true);
        if (n == null) return "balloon failed";
        ((IAnnotation)n.GetAnnotation()).SetPosition2(t[0], t[1], 0);
        return "balloon " + n.GetText();
    }

    // diameter dimension on a coaxial circle edge (z, r) seen face-on in an end view
    public static string DiaOnCircle(string viewName, double z, double r, double[] tp)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        Edge e = FindCircleEdge(v, z, r); if (e == null) return "edge not found";
        double[] t = ToSheet(v, tp[0] / 1000, tp[1] / 1000, tp[2] / 1000);
        doc.ClearSelection2(true); dd.ActivateView(viewName);
        if (!v.SelectEntity(e, false)) return "select failed";
        DisplayDimension d = (DisplayDimension)doc.AddDimension2(t[0], t[1], 0);
        doc.ClearSelection2(true);
        if (d == null) return "dimension failed";
        LastDim = d;
        Dimension dm = (Dimension)d.GetDimension2(0);
        return string.Format("{0} = {1:0.###} mm", dm.FullName, dm.GetSystemValue2("") * 1000);
    }

    // ---------------- exploded view of the top assembly ----------------
    public static string StartExplode(string topPath)
    {
        ISldWorks app = App();
        IModelDoc2 top = (IModelDoc2)app.GetOpenDocumentByName(topPath);
        int ae = 0; app.ActivateDoc3(top.GetTitle(), false, (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref ae);
        IAssemblyDoc asm = (IAssemblyDoc)top;
        string[] names = (string[])asm.GetExplodedViewNames();
        if (names != null && names.Length > 0) return "exploded view exists: " + string.Join(",", names);
        asm.CreateExplodedView();
        names = (string[])asm.GetExplodedViewNames();
        return "created " + (names == null ? "?" : string.Join(",", names));
    }

    // move every leaf component whose path matches one of the regexes along the gearbox axis by dist (mm, +z or -z)
    public static string ExplodeStep(string topPath, string[] patterns, double distMm)
    {
        ISldWorks app = App();
        IModelDoc2 top = (IModelDoc2)app.GetOpenDocumentByName(topPath);
        IAssemblyDoc asm = (IAssemblyDoc)top;
        top.ClearSelection2(true);
        SelectionMgr sm = (SelectionMgr)top.SelectionManager;
        SelectData sd1 = (SelectData)sm.CreateSelectData(); sd1.Mark = 1;
        int n = 0;
        var names = new System.Collections.Generic.List<string>();
        foreach (object o in (object[])asm.GetComponents(false))
        {
            Component2 c = (Component2)o;
            object kids = c.GetChildren();
            if (kids != null && ((object[])kids).Length > 0) continue;
            string path = c.Name2;
            foreach (string pat in patterns)
                if (System.Text.RegularExpressions.Regex.IsMatch(path, pat)) { if (c.Select4(true, sd1, false)) { n++; names.Add(path); } break; }
        }
        if (n == 0) return "nothing selected for " + string.Join("|", patterns);
        // direction: the layout's main axis, mark 2
        SelectData sd2 = (SelectData)sm.CreateSelectData(); sd2.Mark = 2;
        Component2 lay = null;
        foreach (object o in (object[])asm.GetComponents(true)) { Component2 c = (Component2)o; if (c.Name2.StartsWith("00_Gearbox_Master_Layout")) lay = c; }
        Feature ax = (Feature)lay.FeatureByName("AX_Gearbox_Main");
        bool axSel = ax.Select2(true, 2);
        Configuration cfg = (Configuration)top.GetActiveConfiguration();
        int err = 0;
        ExplodeStep st = (ExplodeStep)cfg.AddExplodeStep2(Math.Abs(distMm) / 1000, 0, distMm < 0, 0, 0, false, false, false, out err);
        top.ClearSelection2(true);
        return string.Format("{0} comps, axis={1}, step={2}, err={3}", n, axSel, st == null ? "null" : st.Name, err);
    }

    public static string ExplodedSheet(string modelPath, string format, double scale)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        bool ok = dd.NewSheet4("Exploded", (int)swDwgPaperSizes_e.swDwgPaperA2size, (int)swDwgTemplates_e.swDwgTemplateCustom,
            1, 1, true, format, 0.594, 0.42, "Default", 0, 0, 0, 0, 0, 0);
        dd.ActivateSheet("Exploded");
        IView side = (IView)dd.CreateDrawViewFromModelView3(modelPath, "*Right", 0.30, 0.30, 0);
        IView iso = (IView)dd.CreateDrawViewFromModelView3(modelPath, "*Isometric", 0.30, 0.14, 0);
        string r = "sheet=" + ok;
        foreach (IView v in new IView[] { side, iso })
        {
            if (v == null) { r += " view null"; continue; }
            v.ScaleDecimal = scale;
            v.ShowExploded(true);
            r += " " + v.Name + " exploded=" + v.IsExploded();
        }
        doc.ForceRebuild3(false);
        foreach (IView v in new IView[] { side, iso })
            if (v != null) { double[] o = (double[])v.GetOutline(); r += string.Format(" [{0}: {1:0.000},{2:0.000}-{3:0.000},{4:0.000}]", v.Name, o[0], o[1], o[2], o[3]); }
        return r;
    }

    public static string DeleteBalloons(string viewName)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = FindView((IDrawingDoc)doc, viewName);
        object[] notes = (object[])v.GetNotes();
        doc.ClearSelection2(true);
        int n = 0;
        if (notes != null) foreach (object o in notes) { INote nt = (INote)o; if (nt.IsBomBalloon()) { ((IAnnotation)nt.GetAnnotation()).Select3(true, null); n++; } }
        if (n > 0) doc.EditDelete();
        doc.ClearSelection2(true);
        return n + " balloons deleted";
    }

    public static string DeleteDangling()
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = (IView)((IDrawingDoc)doc).GetFirstView();
        doc.ClearSelection2(true);
        int n = 0;
        while (v != null)
        {
            object[] anns = (object[])v.GetAnnotations();
            if (anns != null) foreach (object o in anns) { IAnnotation a = (IAnnotation)o; if (a.IsDangling()) { a.Select3(true, null); n++; } }
            object[] cms = (object[])v.GetCenterMarks();
            if (cms != null) foreach (object o in cms) { CenterMark c = (CenterMark)o; IAnnotation a = (IAnnotation)c.GetAnnotation(); if (a != null && a.IsDangling()) { a.Select3(true, null); n++; } }
            v = (IView)v.GetNextView();
        }
        if (n > 0) doc.EditDelete();
        doc.ClearSelection2(true);
        return n + " dangling annotations deleted";
    }

    public static string SurfaceCutOnly(string viewName)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = FindView((IDrawingDoc)doc, viewName);
        DrSection s = (DrSection)v.GetSection();
        if (s == null) return "no section";
        s.SetDisplayOnlySurfaceCut(true);
        doc.ForceRebuild3(false);
        return "surface cut only";
    }

    // give every dimension just the decimals its value needs (0, 1 or 2), so 61.5 never shows as 62
    public static string OpenDrawing(string path)
    {
        ISldWorks app = App();
        int e = 0, w = 0;
        IModelDoc2 d = (IModelDoc2)app.OpenDoc6(path, (int)swDocumentTypes_e.swDocDRAWING, (int)swOpenDocOptions_e.swOpenDocOptions_Silent, "", ref e, ref w);
        if (d == null) return "open failed err=" + e;
        int ae = 0;
        app.ActivateDoc3(d.GetTitle(), false, (int)swRebuildOnActivation_e.swRebuildActiveDoc, ref ae);
        return "opened " + d.GetTitle();
    }

    public static string FixPrecision()
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = (IView)((IDrawingDoc)doc).GetFirstView();
        int n = 0;
        while (v != null)
        {
            DisplayDimension d = (DisplayDimension)v.GetFirstDisplayDimension5();
            while (d != null)
            {
                Dimension dm = (Dimension)d.GetDimension2(0);
                double val = dm.GetSystemValue2("") * 1000;
                if (dm.GetType() != (int)swDimensionParamType_e.swDimensionParamTypeDoubleAngular)
                {
                    int p = Math.Abs(val - Math.Round(val)) < 1e-4 ? 0 : (Math.Abs(val * 10 - Math.Round(val * 10)) < 1e-3 ? 1 : 2);
                    // a value like 95.99 that should read 96 is a pick on a 0.01 sliver; keep 2 decimals so it is visible
                    d.SetPrecision3(p, -1, -1, -1);
                    n++;
                }
                d = (DisplayDimension)d.GetNext5();
            }
            v = (IView)v.GetNextView();
        }
        doc.ForceRebuild3(false);
        return n + " dimensions checked";
    }

    public static string SaveActiveAs(string path)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        if (doc.GetType() == (int)swDocumentTypes_e.swDocDRAWING) FixPrecision();
        doc.ClearSelection2(true);
        int e = 0, w = 0;
        bool ok = doc.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref e, ref w);
        return string.Format("{0}: ok={1} err={2} warn={3}", System.IO.Path.GetFileName(path), ok, e, w);
    }

    public static string AutoBalloons(string viewName)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        doc.ClearSelection2(true);
        bool sel = doc.Extension.SelectByID2(viewName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
        AutoBalloonOptions opt = (AutoBalloonOptions)dd.CreateAutoBalloonOptions();
        opt.Layout = (int)swBalloonLayoutType_e.swDetailingBalloonLayout_Square;
        opt.ReverseDirection = false;
        opt.IgnoreMultiple = true;
        opt.InsertMagneticLine = true;
        opt.Style = (int)swBalloonStyle_e.swBS_Circular;
        opt.Size = (int)swBalloonFit_e.swBF_2Chars;
        opt.UpperTextContent = (int)swBalloonTextContent_e.swBalloonTextItemNumber;
        object notes = dd.AutoBalloon5(opt);
        int n = notes == null ? 0 : ((object[])notes).Length;
        doc.ClearSelection2(true);
        return "view selected=" + sel + ", balloons=" + n;
    }

    public static string SetDocProps(string[] kv)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        CustomPropertyManager cpm = doc.Extension.get_CustomPropertyManager("");
        for (int i = 0; i + 1 < kv.Length; i += 2)
            cpm.Add3(kv[i], (int)swCustomInfoType_e.swCustomInfoText, kv[i + 1], (int)swCustomPropertyAddOption_e.swCustomPropertyReplaceValue);
        doc.ForceRebuild3(false);
        return "props set";
    }

    static IView FindView(IDrawingDoc dd, string name)
    {
        IView v = (IView)dd.GetFirstView();
        while (v != null && v.Name != name) v = (IView)v.GetNextView();
        return v;
    }

    static double[] ToSheet(IView v, double x, double y, double z)
    {
        MathUtility mu = (MathUtility)App().GetMathUtility();
        MathPoint p = (MathPoint)mu.CreatePoint(new double[] { x, y, z });
        MathTransform t = (MathTransform)v.ModelToViewTransform;
        MathPoint q = (MathPoint)p.MultiplyTransform(t);
        return (double[])q.ArrayData;
    }

    public static string MapPoint(string viewName, double x, double y, double z)
    {
        IDrawingDoc dd = (IDrawingDoc)App().ActiveDoc;
        double[] s = ToSheet(FindView(dd, viewName), x, y, z);
        return string.Format("({0:0.0000},{1:0.0000})", s[0], s[1]);
    }

    // Linear dimension between two edges picked at model points (mm) of a view; text at a model point.
    public static string DimModel(string viewName, double[] p1, double[] p2, double[] pt, string prefix, string suffix)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        double[] a = ToSheet(v, p1[0] / 1000, p1[1] / 1000, p1[2] / 1000);
        double[] b = ToSheet(v, p2[0] / 1000, p2[1] / 1000, p2[2] / 1000);
        double[] t = ToSheet(v, pt[0] / 1000, pt[1] / 1000, pt[2] / 1000);
        doc.ClearSelection2(true);
        dd.ActivateView(viewName);
        bool s1 = doc.Extension.SelectByID2("", "EDGE", a[0], a[1], 0, false, 0, null, 0);
        bool s2 = doc.Extension.SelectByID2("", "EDGE", b[0], b[1], 0, true, 0, null, 0);
        if (!s1 || !s2) { doc.ClearSelection2(true); return "select failed " + s1 + "/" + s2; }
        DisplayDimension dd2 = (DisplayDimension)doc.AddDimension2(t[0], t[1], 0);
        doc.ClearSelection2(true);
        if (dd2 == null) return "dimension failed";
        dd2.SetPrecision3(DimPrecision, -1, -1, -1);
        if (!string.IsNullOrEmpty(prefix)) dd2.SetText((int)swDimensionTextParts_e.swDimensionTextPrefix, prefix);
        if (!string.IsNullOrEmpty(suffix)) dd2.SetText((int)swDimensionTextParts_e.swDimensionTextSuffix, suffix);
        LastDim = dd2;
        Dimension dm = (Dimension)dd2.GetDimension2(0);
        return string.Format("{0} = {1:0.###} mm", dm.FullName, dm.GetSystemValue2("") * 1000);
    }

    public static DisplayDimension LastDim;

    // coaxial circle edges per part, cached: scanning a gear's edges over COM takes minutes
    static System.Collections.Generic.Dictionary<string, System.Collections.Generic.List<object[]>> circleCache =
        new System.Collections.Generic.Dictionary<string, System.Collections.Generic.List<object[]>>();

    static System.Collections.Generic.List<object[]> CoaxialCircles(IView v)
    {
        IModelDoc2 pd = (IModelDoc2)v.ReferencedDocument;
        string key = pd.GetPathName();
        System.Collections.Generic.List<object[]> list;
        if (circleCache.TryGetValue(key, out list)) return list;
        list = new System.Collections.Generic.List<object[]>();
        foreach (object bo in (object[])((IPartDoc)pd).GetBodies2((int)swBodyType_e.swSolidBody, true))
            foreach (object eo in (object[])((Body2)bo).GetEdges())
            {
                Edge e = (Edge)eo; Curve c = (Curve)e.GetCurve();
                if (!c.IsCircle()) continue;
                double[] cp = (double[])c.CircleParams;
                if (Math.Abs(cp[0]) < 1e-6 && Math.Abs(cp[1]) < 1e-6) list.Add(new object[] { cp[2] * 1000, cp[6] * 1000, e });
            }
        circleCache[key] = list;
        return list;
    }

    static Edge FindCircleEdge(IView v, double zmm, double rmm)
    {
        foreach (object[] o in CoaxialCircles(v))
            if (Math.Abs((double)o[0] - zmm) < 0.01 && Math.Abs((double)o[1] - rmm) < 0.01) return (Edge)o[2];
        return null;
    }

    // Linear dimension between two circular model edges (z, r in mm) seen edge-on in a section; text at model point
    public static string DimCircles(string viewName, double z1, double r1, double z2, double r2, double[] pt, string prefix, string suffix)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        Edge e1 = FindCircleEdge(v, z1, r1), e2 = FindCircleEdge(v, z2, r2);
        if (e1 == null || e2 == null) return "edge not found " + (e1 != null) + "/" + (e2 != null);
        double[] t = ToSheet(v, pt[0] / 1000, pt[1] / 1000, pt[2] / 1000);
        doc.ClearSelection2(true);
        dd.ActivateView(viewName);
        bool s1 = v.SelectEntity(e1, false), s2 = v.SelectEntity(e2, true);
        if (!s1 || !s2) { doc.ClearSelection2(true); return "select failed"; }
        DisplayDimension d = (DisplayDimension)doc.AddDimension2(t[0], t[1], 0);
        doc.ClearSelection2(true);
        if (d == null) return "dimension failed";
        d.SetPrecision3(DimPrecision, -1, -1, -1);
        if (!string.IsNullOrEmpty(prefix)) d.SetText((int)swDimensionTextParts_e.swDimensionTextPrefix, prefix);
        if (!string.IsNullOrEmpty(suffix)) d.SetText((int)swDimensionTextParts_e.swDimensionTextSuffix, suffix);
        LastDim = d;
        Dimension dm = (Dimension)d.GetDimension2(0);
        return string.Format("{0} = {1:0.###} mm", dm.FullName, dm.GetSystemValue2("") * 1000);
    }

    public static string DeleteDim(string fullNameStart)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = (IView)dd.GetFirstView();
        while (v != null)
        {
            DisplayDimension d = (DisplayDimension)v.GetFirstDisplayDimension5();
            while (d != null)
            {
                Dimension dm = (Dimension)d.GetDimension2(0);
                if (dm.FullName.StartsWith(fullNameStart))
                {
                    doc.ClearSelection2(true); ((IAnnotation)d.GetAnnotation()).Select3(false, null); doc.EditDelete(); doc.ClearSelection2(true);
                    return "deleted " + dm.FullName;
                }
                d = (DisplayDimension)d.GetNext5();
            }
            v = (IView)v.GetNextView();
        }
        return "not found";
    }

    // Fit tolerance on the last dimension, e.g. hole=false "k6"
    public static string FitOnLastDim(string fit, bool hole)
    {
        Dimension dm = (Dimension)LastDim.GetDimension2(0);
        DimensionTolerance t = (DimensionTolerance)dm.Tolerance;
        t.Type = (int)swTolType_e.swTolFIT;
        bool ok = hole ? t.SetFitValues(fit, "") : t.SetFitValues("", fit);
        return "fit " + fit + " set=" + ok;
    }

    public static string DatumOnLastDim(string label)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        doc.ClearSelection2(true);
        ((IAnnotation)LastDim.GetAnnotation()).Select3(false, null);
        DatumTag dt = (DatumTag)doc.InsertDatumTag2();
        doc.ClearSelection2(true);
        if (dt == null) return "datum failed";
        dt.SetLabel(label);
        return "datum " + label + " on dimension";
    }

    public static string DatumOnEdge(string viewName, double[] p, string label, double[] tp)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        double[] a = ToSheet(v, p[0] / 1000, p[1] / 1000, p[2] / 1000);
        double[] t = ToSheet(v, tp[0] / 1000, tp[1] / 1000, tp[2] / 1000);
        doc.ClearSelection2(true);
        dd.ActivateView(viewName);
        if (!doc.Extension.SelectByID2("", "EDGE", a[0], a[1], 0, false, 0, null, 0)) return "select failed";
        DatumTag dt = (DatumTag)doc.InsertDatumTag2();
        doc.ClearSelection2(true);
        if (dt == null) return "datum failed";
        dt.SetLabel(label);
        ((IAnnotation)dt.GetAnnotation()).SetPosition2(t[0], t[1], 0);
        return "datum " + label + " on edge";
    }

    public static string DatumOnCircle(string viewName, double z, double r, string label, double[] tp)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        Edge e = FindCircleEdge(v, z, r); if (e == null) return "edge not found";
        double[] t = ToSheet(v, tp[0] / 1000, tp[1] / 1000, tp[2] / 1000);
        doc.ClearSelection2(true); dd.ActivateView(viewName);
        if (!v.SelectEntity(e, false)) return "select failed";
        DatumTag dt = (DatumTag)doc.InsertDatumTag2();
        doc.ClearSelection2(true);
        if (dt == null) return "datum failed";
        dt.SetLabel(label);
        ((IAnnotation)dt.GetAnnotation()).SetPosition2(t[0], t[1], 0);
        return "datum " + label + " on circle edge";
    }

    public static string GtolOnCircle(string viewName, double z, double r, double[] tp, string[] frames)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        Edge e = FindCircleEdge(v, z, r); if (e == null) return "edge not found";
        doc.ClearSelection2(true); dd.ActivateView(viewName);
        if (!v.SelectEntity(e, false)) return "select failed";
        return MakeGtol(doc, v, tp, frames);
    }

    // frames: each string "GCS;dia(0/1);tol;d1;d2;d3" with GCS the swGtolGeomCharSymbol_e name
    public static string GtolOnEdge(string viewName, double[] p, double[] tp, string[] frames)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = FindView(dd, viewName);
        double[] a = ToSheet(v, p[0] / 1000, p[1] / 1000, p[2] / 1000);
        doc.ClearSelection2(true);
        dd.ActivateView(viewName);
        if (!doc.Extension.SelectByID2("", "EDGE", a[0], a[1], 0, false, 0, null, 0)) return "select failed";
        return MakeGtol(doc, v, tp, frames);
    }

    static string MakeGtol(IModelDoc2 doc, IView v, double[] tp, string[] frames)
    {
        double[] t = ToSheet(v, tp[0] / 1000, tp[1] / 1000, tp[2] / 1000);
        Gtol g = (Gtol)doc.InsertGtol();
        doc.ClearSelection2(true);
        if (g == null) return "gtol failed";
        for (int i = 0; i < frames.Length; i++)
        {
            string[] f = frames[i].Split(';');
            if (i > 0) g.AddFrame();
            short gcs = (short)(int)Enum.Parse(typeof(swGtolGeomCharSymbol_e), f[0]);
            g.SetFrameSymbols((short)(i + 1), gcs, f[1] == "1", (short)swGtolMatCondition_e.swMcNONE, false,
                (short)swGtolMatCondition_e.swMcNONE, (short)swGtolMatCondition_e.swMcNONE, (short)swGtolMatCondition_e.swMcNONE, (short)swGtolMatCondition_e.swMcNONE);
            g.SetFrameValues((short)(i + 1), f[2], "", f[3], f[4], f[5]);
        }
        ((IAnnotation)g.GetAnnotation()).SetPosition2(t[0], t[1], 0);
        return "gtol frames=" + frames.Length;
    }

    public static string MoveNoteStartingWith(string start, double x, double y)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        IView v = (IView)dd.GetFirstView();
        while (v != null)
        {
            object[] notes = (object[])v.GetNotes();
            if (notes != null)
                foreach (object o in notes)
                {
                    INote n = (INote)o;
                    if (n.GetText().Contains(start)) { ((IAnnotation)n.GetAnnotation()).SetPosition2(x, y, 0); doc.ForceRebuild3(false); return "moved (in " + v.Name + ")"; }
                }
            v = (IView)v.GetNextView();
        }
        return "not found";
    }

    public static string ModelProp(string path, string name, string value)
    {
        IModelDoc2 d = (IModelDoc2)App().GetOpenDocumentByName(path);
        if (d == null) return "not open";
        CustomPropertyManager cpm = d.Extension.get_CustomPropertyManager("");
        cpm.Add3(name, (int)swCustomInfoType_e.swCustomInfoText, value, (int)swCustomPropertyAddOption_e.swCustomPropertyReplaceValue);
        int e = 0, w = 0; bool ok = d.Save3((int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref e, ref w);
        return "saved=" + ok;
    }

    public static int DimPrecision = 0;

    public static string DeleteViewDims(string viewName)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = FindView((IDrawingDoc)doc, viewName);
        doc.ClearSelection2(true);
        int n = 0;
        DisplayDimension d = (DisplayDimension)v.GetFirstDisplayDimension5();
        while (d != null)
        {
            ((IAnnotation)d.GetAnnotation()).Select3(true, null); n++;
            d = (DisplayDimension)d.GetNext5();
        }
        if (n > 0) doc.EditDelete();
        doc.ClearSelection2(true);
        return n + " dimensions deleted";
    }

    public static string ClearViewAnnotations(string viewName)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = FindView((IDrawingDoc)doc, viewName);
        object[] anns = (object[])v.GetAnnotations();
        if (anns == null) return "0 annotations";
        doc.ClearSelection2(true);
        int n = 0;
        foreach (object o in anns) { if (((IAnnotation)o).Select3(true, null)) n++; }
        doc.EditDelete();
        doc.ClearSelection2(true);
        return n + " annotations deleted";
    }

    public static string SetupSheet(string format, int paper, double w, double h, double scale)
    {
        IDrawingDoc dd = (IDrawingDoc)App().ActiveDoc;
        Sheet s = (Sheet)dd.GetCurrentSheet();
        bool ok = dd.SetupSheet5(s.GetName(), paper, (int)swDwgTemplates_e.swDwgTemplateCustom, scale, 1, true, format, w, h, "Default", true);
        return "sheet setup=" + ok;
    }

    public static string DatumLastDimAt(string label, string viewName, double[] tp)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        string r = DatumOnLastDim(label);
        IView v = FindView((IDrawingDoc)doc, viewName);
        double[] t = ToSheet(v, tp[0] / 1000, tp[1] / 1000, tp[2] / 1000);
        object[] anns = (object[])v.GetAnnotations();
        foreach (object o in anns)
        {
            IAnnotation a = (IAnnotation)o;
            if (a.GetType() == (int)swAnnotationType_e.swDatumTag)
            {
                DatumTag dt = (DatumTag)a.GetSpecificAnnotation();
                if (dt.GetLabel() == label) { a.SetPosition2(t[0], t[1], 0); return r + ", moved"; }
            }
        }
        return r + ", not moved";
    }

    public static string DeleteDatumTags(string label)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = (IView)((IDrawingDoc)doc).GetFirstView();
        int n = 0;
        doc.ClearSelection2(true);
        while (v != null)
        {
            object[] anns = (object[])v.GetAnnotations();
            if (anns != null)
                foreach (object o in anns)
                {
                    IAnnotation a = (IAnnotation)o;
                    if (a.GetType() == (int)swAnnotationType_e.swDatumTag && ((DatumTag)a.GetSpecificAnnotation()).GetLabel() == label)
                    { a.Select3(true, null); n++; }
                }
            v = (IView)v.GetNextView();
        }
        if (n > 0) doc.EditDelete();
        doc.ClearSelection2(true);
        return n + " datum tags '" + label + "' deleted";
    }

    public static string CenterMarks(string viewName)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = FindView((IDrawingDoc)doc, viewName);
        // InsertType 7 = holes + fillets + slots (bitmask: 1 holes, 2 fillets, 4 slots), option 0 = single marks
        bool ok = v.AutoInsertCenterMarks2(1, 0, true, true, true, 0.0025, 0.0015, true, true, 0);
        doc.ForceRebuild3(false);
        int n = 0; v.GetCenterMarkCount2(ref n);
        return "center marks ok=" + ok + " count=" + n;
    }

    // ---------------- automatic dimensioning of turned (revolved about Z) parts ----------------
    class Cyl { public double r, z0, z1; public bool inner; }

    static System.Collections.Generic.List<Cyl> Cylinders(IView v)
    {
        var list = new System.Collections.Generic.List<Cyl>();
        IPartDoc part = (IPartDoc)v.ReferencedDocument;
        foreach (object bo in (object[])part.GetBodies2((int)swBodyType_e.swSolidBody, true))
            foreach (object fo in (object[])((Body2)bo).GetFaces())
            {
                Face2 f = (Face2)fo; Surface s = (Surface)f.GetSurface();
                if (!s.IsCylinder()) continue;
                double[] p = (double[])s.CylinderParams;
                if (Math.Abs(p[0]) > 1e-6 || Math.Abs(p[1]) > 1e-6 || Math.Abs(Math.Abs(p[5]) - 1) > 1e-6) continue;
                double[] box = (double[])f.GetBox();
                var c = new Cyl { r = p[6] * 1000, z0 = box[2] * 1000, z1 = box[5] * 1000, inner = false };
                bool dup = false;
                foreach (var e in list) if (Math.Abs(e.r - c.r) < 0.01 && Math.Abs(e.z0 - c.z0) < 0.01 && Math.Abs(e.z1 - c.z1) < 0.01) dup = true;
                if (!dup) list.Add(c);
            }
        return list;
    }

    static System.Collections.Generic.List<double> PlaneZs(IView v)
    {
        var zs = new System.Collections.Generic.List<double>();
        foreach (object[] o in CoaxialCircles(v))
        {
            double z = Math.Round((double)o[0], 3);
            bool dup = false; foreach (double q in zs) if (Math.Abs(q - z) < 0.01) dup = true;
            if (!dup) zs.Add(z);
        }
        zs.Sort();
        return zs;
    }

    static double MaxRadiusAtZ(IView v, double z)
    {
        double best = -1;
        foreach (object[] o in CoaxialCircles(v))
            if (Math.Abs((double)o[0] - z) < 0.01) best = Math.Max(best, (double)o[1]);
        return best;
    }

    public static string DescribeRevolve(string viewName)
    {
        IView v = FindView((IDrawingDoc)App().ActiveDoc, viewName);
        StringBuilder sb = new StringBuilder();
        foreach (var c in Cylinders(v)) sb.AppendFormat("cyl r={0:0.###} z {1:0.###}..{2:0.###} {3}\n", c.r, c.z0, c.z1, c.inner ? "inner" : "outer");
        sb.Append("circle-edge z: " + string.Join(", ", PlaneZs(v)));
        return sb.ToString();
    }

    // fits: "r=fit" pairs separated by ';' (e.g. "15=k6;27.5=J7"); skipR: radii to leave out; zRef: baseline face z
    public static string AutoDims(string viewName, string fits, string skipR, double zRef, double gap, bool lengths)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IView v = FindView((IDrawingDoc)doc, viewName);
        var fitMap = new System.Collections.Generic.Dictionary<double, string>();
        if (!string.IsNullOrEmpty(fits)) foreach (string kv in fits.Split(';')) { string[] a = kv.Split('='); fitMap[double.Parse(a[0], System.Globalization.CultureInfo.InvariantCulture)] = a[1]; }
        var skip = new System.Collections.Generic.List<double>();
        if (!string.IsNullOrEmpty(skipR)) foreach (string s in skipR.Split(';')) skip.Add(double.Parse(s, System.Globalization.CultureInfo.InvariantCulture));
        var cyls = Cylinders(v);
        double rmax = 0; foreach (var c in cyls) rmax = Math.Max(rmax, c.r);
        cyls.Sort((a, b) => a.z0.CompareTo(b.z0));
        StringBuilder sb = new StringBuilder();
        int k = 0;
        var doneR = new System.Collections.Generic.List<string>();
        foreach (var c in cyls)
        {
            bool sk = false; foreach (double s in skip) if (Math.Abs(s - c.r) < 0.01) sk = true;
            if (sk || c.z1 - c.z0 < 0.3) continue;
            double zm = (c.z0 + c.z1) / 2;
            double ty = -(rmax + gap + LevelStep * k);
            string fit = null; foreach (var kv in fitMap) if (Math.Abs(kv.Key - c.r) < 0.01) fit = kv.Value;
            double rp = c.r - 0.05;   // pick just inside the silhouette line: an exact pick can land on a neighbouring edge
            string res = DimModel(viewName, new double[] { 0, rp, zm }, new double[] { 0, -rp, zm }, new double[] { 0, ty, zm }, "<MOD-DIAM>", "");
            if (LastDim != null && res.Contains("mm"))
            {
                Dimension ldm = (Dimension)LastDim.GetDimension2(0);
                if (ldm.GetType() == (int)swDimensionParamType_e.swDimensionParamTypeDoubleAngular)
                {   // picked a corner on a very short step: drop it rather than leave an angle on the sheet
                    doc.ClearSelection2(true); ((IAnnotation)LastDim.GetAnnotation()).Select3(false, null); doc.EditDelete(); doc.ClearSelection2(true);
                    res = "angular pick removed"; fit = null; LastDim = null;
                }
            }
            if (fit != null && LastDim != null && res.Contains("mm")) FitOnLastDim(fit, char.IsUpper(fit[0]));
            sb.AppendFormat("D{0:0.##} z{1:0.#}: {2}{3}\n", 2 * c.r, zm, res, fit != null ? " " + fit : "");
            k++;
        }
        if (lengths)
        {
            double rRef = MaxRadiusAtZ(v, zRef);
            int j = 0;
            foreach (double z in PlaneZs(v))
            {
                if (Math.Abs(z - zRef) < 0.01) continue;
                double r = MaxRadiusAtZ(v, z);
                double ty = rmax + gap + LevelStep * j;
                string res = DimCircles(viewName, zRef, rRef, z, r, new double[] { 0, ty, (zRef + z) / 2 }, "", "");
                sb.AppendFormat("L z{0:0.##}: {1}\n", z, res);
                j++;
            }
        }
        return sb.ToString();
    }

    // General table with given rows "a|b" at sheet position (top-left)
    public static string GearTable(double x, double y, string[] rows, double colA, double colB)
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        IDrawingDoc dd = (IDrawingDoc)doc;
        TableAnnotation t = (TableAnnotation)dd.InsertTableAnnotation2(false, x, y, (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft, "", rows.Length, 2);
        if (t == null) return "table failed";
        for (int i = 0; i < rows.Length; i++)
        {
            string[] a = rows[i].Split('|');
            t.set_Text(i, 0, a[0]); t.set_Text(i, 1, a.Length > 1 ? a[1] : "");
        }
        t.SetColumnWidth(0, colA, 0); t.SetColumnWidth(1, colB, 0);
        TextFormat tf = (TextFormat)t.GetTextFormat(); tf.CharHeight = 0.0025; t.SetTextFormat(false, tf);
        for (int i = 0; i < rows.Length; i++) t.SetRowHeight(i, 0.0045, 0);
        doc.ForceRebuild3(false);
        return "table rows=" + rows.Length;
    }

    public static double LevelStep = 7.0;

    // Move the parent (front) view and its section; section alignment removed so both can be placed freely
    public static string PlaceViews(double fx, double fy, double sx, double sy)
    {
        return Layout("Section View A-A", "Drawing View1", sx, sy, fx, fy);
    }

    public static string CloseActive()
    {
        ISldWorks app = App();
        IModelDoc2 doc = (IModelDoc2)app.ActiveDoc;
        string t = doc.GetTitle();
        app.CloseDoc(t);
        return "closed " + t;
    }

    public static string BomBox()
    {
        IModelDoc2 doc = (IModelDoc2)App().ActiveDoc;
        ITableAnnotation ta = Bom(doc);
        IAnnotation an = (IAnnotation)ta.GetAnnotation();
        double[] p = (double[])an.GetPosition();
        double w = 0; for (int c = 0; c < ta.ColumnCount; c++) w += ta.GetColumnWidth(c);
        double h = 0; for (int r = 0; r < ta.RowCount; r++) h += ta.GetRowHeight(r);
        return string.Format("anchor=({0:0.000},{1:0.000}) width={2:0.000} height={3:0.000}", p[0], p[1], w, h);
    }
}
