#!/usr/bin/env python3
# Build a satellite map image per trail for the "See the trails" page: fetch Esri World Imagery tiles
# over the trail's bounding box, stitch them, then draw the route (white casing + the trail's identity
# colour) and milestone pins (coloured by type) on top. Writes img/trailmaps/<id>.webp. Tiles are cached
# under _tilecache/ so re-runs are cheap. Attribution (Esri/Maxar/Earthstar Geographics) is shown on the
# page. This replaces the inline-SVG maps with real satellite behind each route (JD 2026-07-11).
import os, sys, re, json, glob, math, io, time, urllib.request

ROOT = r"C:\Users\jwden\WatchApps"
WEB = os.path.join(ROOT, "watchwalks-web")
# Milestones come from the REPO, not a scratchpad. This used to point at one session's temp
# directory (%TEMP%/claude/.../ad05301a-.../scratchpad/story_pass), which has since been
# deleted -- so the tool that builds this site's trail cards was unrunnable, and nobody noticed
# because nobody ran it. A build input that lives in %TEMP% is a build input with an expiry date.
SP = os.path.join(ROOT, "trails")
IMGDIR = os.path.join(WEB, "img", "trailmaps")
CACHE = os.path.join(WEB, "_tilecache")
os.makedirs(IMGDIR, exist_ok=True); os.makedirs(CACHE, exist_ok=True)

from PIL import Image, ImageDraw

# id -> encoded-track shortname (from _gen_trailmaps.py)
TRACK = {"kilimanjaro-lemosho":"lemosho","gr-r2":"grr2",
         # The 2026-07-15 intake added 6 trails and their website cards but no TRACK entries, so
         # 5 of the 6 drew their card map from the MILESTONE list -- overland-track from 14 points
         # instead of 2,275. A missing key here does not fail; it silently draws a worse trail.
         "routeburn-track":"routeburn","overland-track":"overland","kumano-kodo":"kumano",
         "mount-kenya":"mountkenya","otter-trail":"otter",
         "pacific-crest":"pct","length-of-britain":"britain","te-araroa":"teararoa","route-66":"route66",
 "cape-to-cape":"capetocape","tour-du-mont-blanc":"tmb","west-highland-way":"westhighland","john-muir-trail":"jmt",
 "tahoe-rim":"tahoerim","torres-del-paine-w":"torres","australian-alps":"ausalps","haute-route":"hauteroute",
 "long-trail":"longtrail","annapurna-circuit":"annapurna","manaslu-circuit":"manaslu","atlas-traverse":"atlas",
 "inca-road":"incaroad",
 "inca-trail":"inca","jordan-trail":"jordan","larapinta-trail":"larapinta","lycian-way":"lycian",
 "wonderland-trail":"wonderland"}
# Trail identity colour (c1). NOT a copy: read live from the app's TrailArt map, so the site
# cannot drift from the apps the way it already had (12 trails disagreed on 2026-07-13, and the
# palette baked into these .webp route lines was the banned blue/violet one). See _trail_colors.py.
from _trail_colors import C1 as COLOR
# Milestone pins. This was a ten-colour TYPE_COLOR table copied from an app function
# (`milestoneTypeColor`) that NO LONGER EXISTS in the app -- so the website was the last place on
# earth still painting pass/summit #5C82D0 (blue-grey), bridge #9E7BD0 (violet) and landmark
# #CC6FA0 (magenta) -- three colours BRAND s3 bans outright, dotted over all 35 satellite maps in a
# rainbow that belonged to no trail. Under BRAND s11 a trail's nodes wear that TRAIL's colour, so
# the pins are its c1. Start and finish keep the two brand tokens (pine, gold) because "where it
# begins" and "where it ends" are not trail identity, they are the same idea on every trail.
PIN_START  = "#1F5C3D"   # BRAND s3 pine
PIN_FINISH = "#E0A52E"   # BRAND s3 gold


def pin_color(tid, mtype):
    if mtype == "start":
        return PIN_START
    if mtype == "finish":
        return PIN_FINISH
    return COLOR.get(tid, PIN_START)   # the trail's own identity colour
TILE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

def hx(c): return tuple(int(c[i:i+2],16) for i in (1,3,5))

def load_track(tid):
    sn = TRACK.get(tid, tid)
    f = os.path.join(ROOT, sn + "_encoded.txt")
    if os.path.exists(f):
        pts=[]
        for tok in open(f,encoding="utf-8").read().strip().split(";"):
            p=tok.split(",")
            if len(p)==3:
                try: pts.append((float(p[0]),float(p[1]),float(p[2])))
                except: pass
        return pts
    kt = os.path.join(ROOT, sn + "_track_kotlin.txt")
    if os.path.exists(kt):
        pts=[(float(m[0]),float(m[1]),float(m[2])) for m in
             re.findall(r"GeoPoint\(([-0-9.]+)f?,\s*([-0-9.]+),\s*([-0-9.]+)\)", open(kt,encoding="utf-8").read())]
        if pts: return pts
    # TrailGeo.routes — where a trail with NO encoded track keeps its line. The Inca Trail (the FREE
    # hero, the first map anyone sees) lives here with 547 points and was falling straight past this
    # to the milestone list below, drawing its card from 12 points.
    geo = os.path.join(ROOT, r"watchwalks-android\app\src\main\java\com\watchwalks\companion\data\TrailGeo.kt")
    if os.path.exists(geo):
        src = open(geo, encoding="utf-8").read()
        m = re.search(r'"' + re.escape(tid) + r'" to listOf\(', src)
        if m:
            i, depth = m.end(), 1
            while depth and i < len(src):
                if src[i] == "(":
                    depth += 1
                elif src[i] == ")":
                    depth -= 1
                i += 1
            pts = [(float(a), float(b), float(c)) for a, b, c in re.findall(
                r"GeoPoint\(([-0-9.]+)f?,\s*([-0-9.]+),\s*([-0-9.]+)", src[m.end():i - 1])]
            if len(pts) > 2:
                return pts

    # LAST RESORT: the milestone list. This is NOT a route — it is 12-26 points where the real track
    # has thousands, and it draws a crude straight-line fake of the trail. It used to be reached
    # SILENTLY: the 2026-07-15 intake shipped 5 trails whose card map was drawn this way for weeks
    # because TRACK had no id->key entry and nothing said so. Say so.
    mj = os.path.join(ROOT,"trails",tid+".json")
    if os.path.exists(mj):
        d=json.load(open(mj,encoding="utf-8"))
        pts=[(m["km"],m["lat"],m["lng"]) for m in d.get("milestones",[]) if m.get("lat") is not None]
        print(f"  !! {tid}: NO real track found (looked for {sn}_encoded.txt, {sn}_track_kotlin.txt, "
              f"TrailGeo.routes) — falling back to {len(pts)} MILESTONES. The card map will be a "
              f"crude fake. Add an id->key entry to TRACK.")
        return pts
    return []

def merc(lat,lng,z):
    lat=max(-85.05,min(85.05,lat))   # web mercator is undefined at the poles; clamp to its valid range
    n=2**z; x=(lng+180)/360*n*256
    la=math.radians(lat)
    y=(1-math.log(math.tan(la)+1/math.cos(la))/math.pi)/2*n*256
    return x,y

def pick_zoom(pts, target_w=680, target_h=430, pad=0.10, zmin=2, zmax=15):
    lats=[p[1] for p in pts]; lngs=[p[2] for p in pts]
    for z in range(zmax, zmin-1, -1):
        xs=[merc(la,lo,z)[0] for la,lo in zip(lats,lngs)]
        ys=[merc(la,lo,z)[1] for la,lo in zip(lats,lngs)]
        w=(max(xs)-min(xs))*(1+2*pad); h=(max(ys)-min(ys))*(1+2*pad)
        if w<=target_w and h<=target_h:
            return z
    return zmin

def fetch_tile(z,x,y):
    n=2**z; x%=n; y=max(0,min(n-1,y))
    cf=os.path.join(CACHE,f"{z}_{y}_{x}.jpg")
    if os.path.exists(cf):
        try: return Image.open(cf).convert("RGB")
        except: pass
    url=TILE.format(z=z,x=x,y=y)
    for att in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"WatchWalks-mapgen/1.0"})
            data=urllib.request.urlopen(req,timeout=25).read()
            open(cf,"wb").write(data)
            return Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:
            time.sleep(0.6*(att+1))
    return Image.new("RGB",(256,256),(40,44,40))

def build(tid, track, milestones):
    color=hx(COLOR.get(tid,"#4E9E5A"))
    W,H=680,430; pad=0.10
    z=pick_zoom(track,W,H,pad)
    xs=[merc(la,lo,z)[0] for _,la,lo in track]; ys=[merc(la,lo,z)[1] for _,la,lo in track]
    minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)
    cx=(minx+maxx)/2; cy=(miny+maxy)/2
    # canvas centered on route center, fixed W×H
    ox=cx-W/2; oy=cy-H/2
    # tile range
    tx0=int(ox//256); tx1=int((ox+W)//256); ty0=int(oy//256); ty1=int((oy+H)//256)
    canvas=Image.new("RGB",((tx1-tx0+1)*256,(ty1-ty0+1)*256))
    for ty in range(ty0,ty1+1):
        for tx in range(tx0,tx1+1):
            canvas.paste(fetch_tile(z,tx,ty),((tx-tx0)*256,(ty-ty0)*256))
    # crop to the W×H window
    cropx=int(ox-tx0*256); cropy=int(oy-ty0*256)
    img=canvas.crop((cropx,cropy,cropx+W,cropy+H)).convert("RGB")
    # slight darken for route legibility
    ov=Image.new("RGB",(W,H),(0,0,0)); img=Image.blend(img,ov,0.12)
    dr=ImageDraw.Draw(img,"RGBA")
    pl=[(x-ox,y-oy) for x,y in zip(xs,ys)]
    dr.line(pl,fill=(255,255,255,235),width=7,joint="curve")
    dr.line(pl,fill=color+(255,),width=4,joint="curve")
    # pins
    tk=[p[0] for p in track]
    for m in milestones:
        j=min(range(len(track)),key=lambda i:abs(track[i][0]-m["km"]))
        px=xs[j]-ox; py=ys[j]-oy
        c=hx(pin_color(tid,m["type"]))
        r=4.5
        dr.ellipse([px-r-1.4,py-r-1.4,px+r+1.4,py+r+1.4],fill=(255,255,255,255))
        dr.ellipse([px-r,py-r,px+r,py+r],fill=c+(255,))
    out=os.path.join(IMGDIR,tid+".webp")
    img.save(out,"WEBP",quality=82,method=6)
    return out

def main():
    src=open(os.path.join(ROOT,r"watchwalks-android\app\src\main\java\com\watchwalks\companion\data\SampleData.kt"),encoding="utf-8").read()
    ids=[m.group(1) for m in re.finditer(r'Trail\("([a-z0-9-]+)"',src)]
    # Optional id filter. Without it this rebuilds all 41 webps, which churns 38 files nobody asked
    # to change and buries the one you actually added in the diff.
    only=[a for a in sys.argv[1:] if not a.startswith("-")]
    if only:
        missing=[o for o in only if o not in ids]
        if missing: raise SystemExit(f"not in SampleData: {missing}")
        ids=[i for i in ids if i in only]
    done=0
    for tid in ids:
        # The South Pole sits where web mercator is undefined and there is no meaningful satellite
        # imagery at the pole, so it keeps the clean inline-SVG route instead.
        if tid=="south-pole-last-degree": print("  SKIP",tid,"(pole: uses SVG)"); continue
        track=load_track(tid)
        if len(track)<2: print("  SKIP",tid,"(no route)"); continue
        ms=json.load(open(os.path.join(SP,tid+".json"),encoding="utf-8"))["milestones"]
        build(tid,track,ms); done+=1
        print(f"  {tid}: satellite map built ({len(track)} route pts, {len(ms)} pins)")
    print(f"built {done} satellite maps -> {IMGDIR}")

if __name__=="__main__":
    main()
