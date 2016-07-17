#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import glob
import json
import math
import os
import re
import sys
from copy import deepcopy
from os.path import (
    abspath,
    basename,
)
from textwrap import dedent as d

from lxml import etree
from lxml.builder import E
from tqdm import tqdm

import bezier_cubic
from settings import *
from svg.path import parse_path


def compute_path_len(path):
    return parse_path(path).length(error=1e-8)


def shescape(path):
    return "'"+re.sub(r"(?=['\\\\])","\\\\",path)+"'"


# ease, ease-in, etc:
# https://developer.mozilla.org/en-US/docs/Web/CSS/timing-function#ease
pt1 = bezier_cubic.pt(0,0)
ease_ct1 = bezier_cubic.pt(0.25, 0.1)
ease_ct2 = bezier_cubic.pt(0.25, 1.0)
ease_in_ct1 = bezier_cubic.pt(0.42, 0.0)
ease_in_ct2 = bezier_cubic.pt(1.0, 1.0)
ease_in_out_ct1 = bezier_cubic.pt(0.42, 0.0)
ease_in_out_ct2 = bezier_cubic.pt(0.58, 1.0)
ease_out_ct1 = bezier_cubic.pt(0.0, 0.0)
ease_out_ct2 = bezier_cubic.pt(0.58, 1.0)
pt2 = bezier_cubic.pt(1,1)


def linear(x):
    return x


def ease(x):
    return bezier_cubic.value(pt1, ease_ct1, ease_ct2, pt2, x)


def ease_in(x):
    return bezier_cubic.value(pt1, ease_in_ct1, ease_in_ct2, pt2, x)


def ease_in_out(x):
    return bezier_cubic.value(pt1, ease_in_out_ct1, ease_in_out_ct2, pt2, x)


def ease_out(x):
    return bezier_cubic.value(pt1, ease_out_ct1, ease_out_ct2, pt2, x)


timing_funcs = {
    'linear': linear,
    'ease': ease,
    'ease-in': ease_in,
    'ease-in-out': ease_in_out,
    'ease-out': ease_out
}

if not TIMING_FUNCTION in timing_funcs:
    exit('Sorry, invalid timing function "%s"', TIMING_FUNCTION)
my_timing_func = timing_funcs[TIMING_FUNCTION]

# we will need this to deal with svg
namespaces = {'n': "http://www.w3.org/2000/svg"}
etree.register_namespace("xlink","http://www.w3.org/1999/xlink")
parser = etree.XMLParser(remove_blank_text=True)


def _sanity_check_gif(generate_gif):
    if generate_gif and GIF_BACKGROUND_COLOR == 'transparent' and not GIF_ALLOW_TRANSPARENT:
        exit(d("""
        ******************************************************************
        WARNING: "transparent" not allowed by default as gif background,
        because generated files are 10x bigger. If you are really sure
        set GIF_ALLOW_TRANSPARENT to True in settings.py and rerun.
        ******************************************************************
        """))


def create_animation(
    filename,
    generate_svg=True,
    generate_js_svg=False,
    generate_gif=False,
):
    _sanity_check_gif(generate_gif)

    filename_noext = re.sub(r'\.[^\.]+$','',filename)
    filename_noext_ascii = re.sub(r'\\([\\u])','\\1',
                            json.dumps(filename_noext))[1:-1]
    baseid = basename(filename_noext_ascii)

    # load xml
    doc = etree.parse(filename, parser)

    # for xlink namespace introduction
    doc.getroot().set('{http://www.w3.org/1999/xlink}used','')

    #clear all extra elements this program may have previously added
    for el in doc.xpath("/n:svg/n:style", namespaces=namespaces):
        if re.match( r'-Kanimaji$', g.get('id') ):
            doc.getroot().remove(el)
    for g in doc.xpath("/n:svg/n:g", namespaces=namespaces):
        if re.match( r'-Kanimaji$', g.get('id') ):
            doc.getroot().remove(g)

    # create groups with a copies (references actually) of the paths
    bg_g = E.g(id = 'kvg:'+baseid+'-bg-Kanimaji',
            style = ('fill:none;stroke:%s;stroke-width:%f;'+
                'stroke-linecap:round;stroke-linejoin:round;') %
                (STOKE_UNFILLED_COLOR, STOKE_UNFILLED_WIDTH) )
    anim_g = E.g(id = 'kvg:'+baseid+'-anim-Kanimaji',
            style = ('fill:none;stroke:%s;stroke-width:%f;'+
                'stroke-linecap:round;stroke-linejoin:round;') %
                (STOKE_FILLED_COLOR, STOKE_FILLED_WIDTH) )
    if SHOW_BRUSH:
        brush_g = E.g(id = 'kvg:'+baseid+'-brush-Kanimaji',
                style = ('fill:none;stroke:%s;stroke-width:%f;'+
                'stroke-linecap:round;stroke-linejoin:round;') %
                (BRUSH_COLOR, BRUSH_WIDTH))
        brush_brd_g = E.g(id = 'kvg:'+baseid+'-brush-brd-Kanimaji',
                style = ('fill:none;stroke:%s;stroke-width:%f;'+
                'stroke-linecap:round;stroke-linejoin:round;') %
                (BRUSH_BORDER_COLOR, BRUSH_BORDER_WIDTH))

    # compute total length and time, at first
    totlen = 0
    tottime = 0

    for g in doc.xpath("/n:svg/n:g", namespaces=namespaces):
        if re.match( r'^kvg:StrokeNumbers_', g.get('id') ):
            continue
        for p in g.xpath(".//n:path", namespaces=namespaces):
            pathlen = compute_path_len(p.get('d'))
            duration = stroke_length_to_duration(pathlen)
            totlen += pathlen
            tottime += duration

    animation_time = time_rescale(tottime) #math.pow(3 * tottime, 2.0/3)
    tottime += WAIT_AFTER * tottime / animation_time
    actual_animation_time = animation_time
    animation_time += WAIT_AFTER

    css_header = d("""
    /* CSS automatically generated by kanimaji.py, do not edit! */
    """)
    if generate_svg:
        animated_css = css_header
    if generate_js_svg:
        js_animated_css = css_header + d("""
            .backward {
                animation-direction: reverse !important;
            }
            """)
        js_anim_els = []  # collect the ids of animating elements
        js_anim_time = [] # the time set (as default) for each animation
    if GENERATE_GIF:
        static_css = {}
        last_frame_index = int(actual_animation_time/GIF_FRAME_DURATION)+1
        for i in range(0, last_frame_index+1):
            static_css[i] = css_header
        last_frame_delay = animation_time - last_frame_index*GIF_FRAME_DURATION
    elapsedlen = 0
    elapsedtime = 0

    # add css elements for all strokes
    for g in doc.xpath("/n:svg/n:g", namespaces=namespaces):
        groupid = g.get('id')
        if re.match( r'^kvg:StrokeNumbers_', groupid ):
            rule = d("""
                #%s {
                    display: none;
                }""" % re.sub(r':', '\\\\3a ', groupid))
            if generate_svg:
                animated_css += rule
            if generate_js_svg:
                js_animated_css += rule
            if GENERATE_GIF:
                for k in static_css: static_css[k] += rule
            continue

        gidcss = re.sub(r':', '\\\\3a ', groupid)
        rule = d("""
            #%s {
                stroke-width: %.01fpx !important;
                stroke:       %s !important;
            }""" % (gidcss, STOKE_BORDER_WIDTH, STOKE_BORDER_COLOR))
        if generate_svg:
            animated_css += rule
        if generate_js_svg:
            js_animated_css += rule
        if GENERATE_GIF:
            for k in static_css: static_css[k] += rule

        for p in g.xpath(".//n:path", namespaces=namespaces):
            pathid = p.get('id')
            pathidcss = re.sub(r':', '\\\\3a ', pathid)

            if generate_js_svg:
                js_anim_els.append({})

            bg_pathid = pathid+'-bg'
            bg_pathidcss = pathidcss+'-bg'
            ref = E.use(id = bg_pathid)
            ref.set('{http://www.w3.org/1999/xlink}href','#'+pathid)
            bg_g.append(ref)
            if generate_js_svg:
                js_anim_els[-1]["bg"] = ref

            anim_pathid = pathid+'-anim'
            anim_pathidcss = pathidcss+'-anim'
            ref = E.use(id = anim_pathid)
            ref.set('{http://www.w3.org/1999/xlink}href','#'+pathid)
            anim_g.append(ref)
            if generate_js_svg:
                js_anim_els[-1]["anim"] = ref

            if SHOW_BRUSH:
                brush_pathid = pathid+'-brush'
                brush_pathidcss = pathidcss+'-brush'
                ref = E.use(id = brush_pathid)
                ref.set('{http://www.w3.org/1999/xlink}href','#'+pathid)
                brush_g.append(ref)
                if generate_js_svg:
                    js_anim_els[-1]["brush"] = ref

                brush_brd_pathid = pathid+'-brush-brd'
                brush_brd_pathidcss = pathidcss+'-brush-brd'
                ref = E.use(id = brush_brd_pathid)
                ref.set('{http://www.w3.org/1999/xlink}href','#'+pathid)
                brush_brd_g.append(ref)
                if generate_js_svg:
                    js_anim_els[-1]["brush-brd"] = ref

            pathname = re.sub(r'^kvg:','',pathid)
            pathlen = compute_path_len(p.get('d'))
            duration = stroke_length_to_duration(pathlen)
            relduration = duration * tottime / animation_time # unscaled time
            if generate_js_svg:
                js_anim_time.append(relduration)
            newelapsedlen = elapsedlen + pathlen
            newelapsedtime = elapsedtime + duration
            anim_start = elapsedtime/tottime*100
            anim_end = newelapsedtime/tottime*100

            if generate_svg:
                # animation stroke progression
                animated_css += d("""
                    @keyframes strike-%s {
                        0%% { stroke-dashoffset: %.03f; }
                        %.03f%% { stroke-dashoffset: %.03f; }
                        %.03f%% { stroke-dashoffset: 0; }
                        100%% { stroke-dashoffset: 0; }
                    }""" % (pathname, pathlen, anim_start, pathlen, anim_end))

                # animation visibility
                animated_css += d("""
                    @keyframes showhide-%s {
                        %.03f%% { visibility: hidden; }
                        %.03f%% { stroke: %s; }
                    }""" % (pathname, anim_start, anim_end, STOKE_FILLING_COLOR))

                # animation progression
                animated_css += d("""
                    #%s {
                        stroke-dasharray: %.03f %.03f;
                        stroke-dashoffset: 0;
                        animation: strike-%s %.03fs %s infinite,
                            showhide-%s %.03fs step-start infinite;
                    }""" % (anim_pathidcss, pathlen, pathlen,
                            pathname, animation_time,
                            TIMING_FUNCTION,
                            pathname, animation_time))

                if SHOW_BRUSH:
                    # brush element visibility
                    animated_css += d("""
                        @keyframes showhide-brush-%s {
                            %.03f%% { visibility: hidden; }
                            %.03f%% { visibility: visible; }
                            100%% { visibility: hidden; }
                        }""" % (pathname, anim_start, anim_end))

                    # brush element progression
                    animated_css += d("""
                        #%s, #%s {
                            stroke-dasharray: 0 %.03f;
                            animation: strike-%s %.03fs %s infinite,
                                showhide-brush-%s %.03fs step-start infinite;
                        }""" % (brush_pathidcss, brush_brd_pathidcss,
                            pathlen,
                            pathname, animation_time, TIMING_FUNCTION,
                            pathname, animation_time))

            if generate_js_svg:
                js_animated_css += d("""\n
                    /* stroke %s */""" % pathid)

                # brush and background hidden by default
                if SHOW_BRUSH:
                    js_animated_css += d("""
                        #%s, #%s, #%s {
                            visibility: hidden;
                        }""") % (brush_pathidcss, brush_brd_pathidcss, bg_pathidcss)

                # hide stroke after current element
                after_curr = '[class *= "current"]'
                js_animated_css += d("""
                    %s ~ #%s {
                        visibility: hidden;
                    }""") % (after_curr, anim_pathidcss)

                # and show bg after current element, or if animated
                js_animated_css += d("""
                    %s ~ #%s, #%s.animate {
                        visibility: visible;
                    }""") % (after_curr, bg_pathidcss, bg_pathidcss)

                # animation stroke progression
                js_animated_css += d("""
                    @keyframes strike-%s {
                        0%% { stroke-dashoffset: %.03f; }
                        100%% { stroke-dashoffset: 0; }
                    }""" % (pathname, pathlen))

                js_animated_css += d("""
                    #%s.animate {
                        stroke: %s;
                        stroke-dasharray: %.03f %.03f;
                        visibility: visible;
                        animation: strike-%s %.03fs %s forwards 1;
                    }""" % (anim_pathidcss,
                            STOKE_FILLING_COLOR,
                            pathlen, pathlen,
                            pathname, relduration, TIMING_FUNCTION))
                if SHOW_BRUSH:
                    js_animated_css += d("""
                        @keyframes strike-brush-%s {
                            0%% { stroke-dashoffset: %.03f; }
                            100%% { stroke-dashoffset: 0.4; }
                        }""" % (pathname, pathlen))
                    js_animated_css += d("""
                        #%s.animate.brush, #%s.animate.brush {
                            stroke-dasharray: 0 %.03f;
                            visibility: visible;
                            animation: strike-brush-%s %.03fs %s forwards 1;
                        }""") % (brush_pathidcss, brush_brd_pathidcss,
                                pathlen,
                                pathname, relduration, TIMING_FUNCTION)

            if GENERATE_GIF:
                for k in static_css:
                    time = k * GIF_FRAME_DURATION
                    reltime = time * tottime / animation_time # unscaled time

                    static_css[k] += d("""
                    /* stroke %s */
                    """ % pathid)

                    # animation
                    if reltime < elapsedtime: #just hide everything
                        rule = "#%s" % anim_pathidcss
                        if SHOW_BRUSH:
                            rule += ", #%s, #%s" % (brush_pathidcss, brush_brd_pathidcss)
                        static_css[k] += d("""
                            %s {
                                visibility: hidden;
                            }""" % rule)
                    elif reltime > newelapsedtime: #just hide the brush, and bg
                        rule = "#%s" % bg_pathidcss
                        if SHOW_BRUSH:
                            rule += ", #%s, #%s" % (brush_pathidcss, brush_brd_pathidcss)
                        static_css[k] += d("""
                            %s {
                                visibility: hidden;
                            }""" % (rule))
                    else:
                        intervalprop = ((reltime-elapsedtime) /
                                    (newelapsedtime-elapsedtime))
                        progression = my_timing_func(intervalprop)
                        static_css[k] += d("""
                            #%s {
                                stroke-dasharray: %.03f %.03f;
                                stroke-dashoffset: %.04f;
                                stroke: %s;
                            }""" % (anim_pathidcss, pathlen, pathlen+0.002,
                                pathlen * (1-progression)+0.0015,
                                STOKE_FILLING_COLOR))
                        if SHOW_BRUSH:
                            static_css[k] += d("""
                                #%s, #%s {
                                    stroke-dasharray: 0.001 %.03f;
                                    stroke-dashoffset: %.04f;
                                }""" % (brush_pathidcss, brush_brd_pathidcss,
                                    pathlen+0.002,
                                    pathlen * (1-progression)+0.0015))

            elapsedlen = newelapsedlen
            elapsedtime = newelapsedtime


    # insert groups
    if SHOW_BRUSH and not SHOW_BRUSH_FRONT_BORDER:
        doc.getroot().append(brush_brd_g)
    doc.getroot().append(bg_g)
    if SHOW_BRUSH and SHOW_BRUSH_FRONT_BORDER:
        doc.getroot().append(brush_brd_g)
    doc.getroot().append(anim_g)
    if SHOW_BRUSH:
        doc.getroot().append(brush_g)

    if generate_svg:
        style = E.style(animated_css, id="style-Kanimaji")
        doc.getroot().insert(0, style)
        svgfile = filename_noext + '_anim.svg'
        output_dir = os.path.join(OUTPUT_DIR, 'svg')
        try:
            os.makedirs(output_dir)
        except OSError:
            pass
        output_path = os.path.join(output_dir, os.path.basename(svgfile))
        doc.write(output_path, pretty_print=True)
        doc.getroot().remove(style)

    if GENERATE_GIF:
        svgframefiles = []
        pngframefiles = []
        svgexport_data = []
        for k in static_css:
            svgframefile = filename_noext_ascii + ("_frame%04d.svg"%k)
            pngframefile = filename_noext_ascii + ("_frame%04d.png"%k)
            svgframefiles.append(svgframefile)
            pngframefiles.append(pngframefile)
            svgexport_data.append({"input": [abspath(svgframefile)],
                                   "output": [[abspath(pngframefile),
                                                 "%d:%d"% (GIF_SIZE, GIF_SIZE)]]})

            style = E.style(static_css[k], id="style-Kanimaji")
            doc.getroot().insert(0, style)
            output_dir = os.path.join(OUTPUT_DIR, 'gif')
            try:
                os.makedirs(output_dir)
            except OSError:
                pass
            output_path = os.path.join(output_dir, os.path.basename(svgframefile))
            doc.write(output_path, pretty_print=True)
            doc.getroot().remove(style)

        # create json file
        svgexport_datafile = filename_noext_ascii+"_export_data.json"
        with open(svgexport_datafile,'w') as f:
            f.write(json.dumps(svgexport_data))
        print 'created instructions %s' % svgexport_datafile

        # run svgexport
        cmdline = 'svgexport %s' % shescape(svgexport_datafile)
        print cmdline
        if os.system(cmdline) != 0:
            exit('Error running external command')

        if DELETE_TEMPORARY_FILES:
            os.remove(svgexport_datafile)
            for f in svgframefiles:
                os.remove(f)

        # generate GIF
        giffile_tmp1 = filename_noext + '_anim_tmp1.gif'
        giffile_tmp2 = filename_noext + '_anim_tmp2.gif'
        giffile = filename_noext + '_anim.gif'
        escpngframefiles = ' '.join(shescape(f) for f in pngframefiles[0:-1])

        if GIF_BACKGROUND_COLOR == 'transparent':
            bgopts = '-dispose previous'
        else:
            bgopts = "-background '%s' -alpha remove" % GIF_BACKGROUND_COLOR
        cmdline = ("convert -delay %d %s -delay %d %s "+
                    "%s -layers OptimizePlus %s") % (
                    int(GIF_FRAME_DURATION*100),
                    escpngframefiles,
                    int(last_frame_delay*100),
                    shescape(pngframefiles[-1]),
                    bgopts,
                    shescape(giffile_tmp1))
        print cmdline
        if os.system(cmdline) != 0:
            exit('Error running external command')

        if DELETE_TEMPORARY_FILES:
            for f in pngframefiles:
                os.remove(f)
            print 'cleaned up.'

        cmdline = ("convert %s \\( -clone 0--1 -background none "+
                   "+append -quantize transparent -colors 63 "+
                   "-unique-colors -write mpr:cmap +delete \\) "+
                   "-map mpr:cmap %s") % (
                    shescape(giffile_tmp1),
                    shescape(giffile_tmp2))
        print cmdline
        if os.system(cmdline) != 0:
            exit('Error running external command')
        if DELETE_TEMPORARY_FILES:
            os.remove(giffile_tmp1)

        cmdline = ("gifsicle -O3 %s -o %s") % (
                    shescape(giffile_tmp2),
                    shescape(giffile))
        print cmdline
        if os.system(cmdline) != 0:
            exit('Error running external command')
        if DELETE_TEMPORARY_FILES:
            os.remove(giffile_tmp2)

    if generate_js_svg:
        f0insert = [bg_g, anim_g]
        if SHOW_BRUSH: f0insert += [brush_g, brush_brd_g]
        for g in f0insert:
            el = E.a()
            el.set("data-stroke","0")
            g.insert(0, el)

        for i in range(0, len(js_anim_els)):
            els = js_anim_els[i]
            for k in els:
                els[k].set("data-stroke",str(i+1))
            els["anim"].set("data-duration", str(js_anim_time[i]))

        doc.getroot().set('data-num-strokes', str(len(js_anim_els)))

        style = E.style(js_animated_css, id="style-Kanimaji")
        doc.getroot().insert(0, style)
        svgfile = filename_noext + '_js_anim.svg'
        output_dir = os.path.join(OUTPUT_DIR, 'js_svg')
        try:
            os.makedirs(output_dir)
        except OSError:
            pass
        output_path = os.path.join(output_dir, os.path.basename(svgfile))
        doc.write(output_path, pretty_print=True)
        doc.getroot().remove(style)


def clear_converted():
    for ext in ['svg', 'gif']:
        for converted_file in glob.glob(os.path.join(OUTPUT_DIR, '*.' + ext)):
            os.remove(converted_file)


def create_animations():
    for svg_path in tqdm(
        glob.glob(os.path.join(KANJIVG_SVG_DIR, '*.svg')),
        mininterval=0.5, miniters=5
    ):
        create_animation(svg_path)


def _parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--svg', dest='generate_svg', default=True)
    parser.add_argument('--js-svg', dest='generate_js_svg', default=False)
    parser.add_argument('--gif', dest='generate_gif', default=False)
    return parser.parse_args()


if __name__ == '__main__':
    options = _parse_arguments()

    clear_converted()
    create_animations(
        generate_svg=options.generate_svg,
        generate_js_svg=options.generate_js_svg,
        generate_gif=options.generate_gif,
    )
