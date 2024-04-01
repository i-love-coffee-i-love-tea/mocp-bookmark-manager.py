#!/usr/bin/env python3
#encoding=utf-8

import urwid
import sys
import sqlite3
from os.path import expanduser
import os
import subprocess
import shutil
import time
# for retry decorator
import functools

MAX_RATING=6
MOCP_DELAY=0.15

class SignalWrap(urwid.WidgetWrap):

    def __init__(self, w, is_preemptive=False):
        urwid.WidgetWrap.__init__(self, w)
        self.event_listeners = []
        self.is_preemptive = is_preemptive

    def listen(self, mask, handler):
        self.event_listeners.append((mask, handler))

    def keypress(self, size, key):
        result = key

        if self.is_preemptive:
            for mask, handler in self.event_listeners:
                if mask is None or mask == key:
                    result = handler(self, size, key)
                    break

        if result is not None:
            result = self._w.keypress(size, key)

        if result is not None and not self.is_preemptive:
            for mask, handler in self.event_listeners:
                if mask is None or mask == key:
                    return handler(self, size, key)

        return result

class MocController():

    mocp_binary = '/usr/bin/mocp'
    max_retries = 5

    def get_volume(self):
        return '▁▂▃▄▅▆▇█'

    def get_player_state(self):
        cmd = '%s -Q "%%state"' % (self.mocp_binary)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout = [x.decode('utf-8').rstrip('\n') for x in iter(proc.stdout.readlines())]
        stderr = [x.decode('utf-8').rstrip('\n') for x in iter(proc.stderr.readlines())]
        proc.stdout.close()
        
        if len(stdout) > 0:
            if 'PLAY' in stdout[0]:
                return "%s, position: %ss" % (stdout[0], self.get_playing_pos())
            else:
                return stdout[0]
        else:
            if len(stderr) > 1 and "server is not running" in stderr[1]:
                return "not running"
            elif len(stderr) > 0:
                return stderr[0]
            else:
                return "error"

    def toggle_pause(self):
        cmd = '%s --toggle-pause' % (self.mocp_binary)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        proc.stdout.close()

    def play_file(self, filepath):
        if self.get_player_state() == "not running":
            self.start_moc_player()
        cmd = '%s -l "%s"' % (self.mocp_binary, filepath)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdout.close()
        return proc.returncode == 0
    
    def start_moc_player(self):
        cmd = '%s --server' % self.mocp_binary
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        proc.stdout.close()
        time.sleep(MOCP_DELAY)

    def jump_to_second(self, second, retries=5):
        cmd = '%s -j %ss' % (self.mocp_binary, second)
        proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE)
        stderr = [x.decode('utf-8').rstrip('\n') for x in iter(proc.stderr.readlines())]
        retries_done = 0
        while len(stderr) > 0 and retries_done < retries:
            proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE)
            stderr = [x.decode('utf-8').rstrip('\n') for x in iter(proc.stderr.readlines())]
            time.sleep(MOCP_DELAY)
            retries_done += 1


        proc.stderr.close()

    def rewind(self, seconds):
        foo = "%s" % 6
        cmd = '%s --seek -%s' % (self.mocp_binary, seconds)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        proc.stdout.close()

    def skip(self, seconds):
        cmd = '%s --seek %s' % (self.mocp_binary, seconds)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        proc.stdout.close()

    def get_playing_file(self):
        cmd = '%s -Q "%%file"' % (self.mocp_binary)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        stdout = [x.decode('utf-8').rstrip('\n') for x in iter(proc.stdout.readlines())]
        proc.stdout.close()
        return stdout[0]

    def get_playing_pos(self):
        cmd = '%s -Q %%cs' % (self.mocp_binary)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        stdout = [x.decode('utf-8').rstrip('\n') for x in iter(proc.stdout.readlines())]
        proc.stdout.close()
        if len(stdout) > 0:
            return stdout[0]
        else:
            return -1



    def retry(retry_count=5, delay=0.1, allowed_exceptions=()):
        def decorator(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                for _ in range(retry_count):
                    try:
                        if func(*func_args):
                            return True
                    except:
                        pass
                        log.debug("wating for %s seconds before retrying again")
                        sleep(delay)
                    # everything in here would be the same

            return wrapper
        return decorator
    

class BookmarkDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(expanduser('~/Radio_X/mocp-bookmarks.sqlite'))
        #self.conn = sqlite3.connect(expanduser('/mnt/nas2/morpheus_20201109/home/Radio_X/mocp-bookmarks.sqlite'))
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER PRIMARY KEY, datetime_created TEXT, name TEXT, position INTEGER, rating INTEGER, comment TEXT)''')
        cursor.close()
        self.conn.commit()

    def add(self, filename, position, rating="NULL", comment=""):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO bookmarks (name, rating, position, comment) VALUES ('%s', %s, %s, '%s')" % (filename, str(rating), position, comment))
        cursor.close()
        self.conn.commit()
        return

    def delete(self, bookmark_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM bookmarks WHERE id=%s" % (bookmark_id))
        cursor.close()
        self.conn.commit()
        return

    def update(self, bookmark_id, rating="NULL", comment="NULL"):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE bookmarks SET rating=%s, comment='%s' WHERE id=%s" % (str(rating), comment, bookmark_id))
        cursor.close()
        self.conn.commit()
        return

    def get_all(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, rating, position, comment FROM bookmarks ORDER BY id ASC, position ASC")
        return cursor.fetchall()

    def get_filtered(self, filter_string):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, rating, position, comment FROM bookmarks WHERE name LIKE '%%%s%%' OR comment LIKE '%%%s%%' ORDER BY name ASC, position ASC" % (filter_string, filter_string))
        return cursor.fetchall()

    def get_next_bookmark(self, filename, position):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, rating, position, comment FROM bookmarks WHERE name='%s' and position > %s ORDER BY name ASC, position ASC" % (filename, position))
        return cursor.fetchone()

    def get_previous_bookmark(self, filename, position):
        cursor = self.conn.cursor()
        zapping_tolerance = 1 
        position = int(position) - zapping_tolerance
        cursor.execute("SELECT id, name, rating, position, comment FROM bookmarks WHERE name='%s' and position < %s ORDER BY name ASC, position DESC" % (filename, position))
        return cursor.fetchone()

    def get_bookmarks_by_file(self, filepath):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, rating, position, comment FROM bookmarks WHERE name='%s' ORDER BY position ASC" % (filepath))
        return cursor.fetchall()

    def get_bookmarks_by_rating(self, rating, comparisonOperator=">=", filepath=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, rating, position, comment FROM bookmarks WHERE rating%s%s ORDER BY name ASC, position ASC" % (comparisonOperator, rating))
        return cursor.fetchall()

    def get_bookmarks_by_comment(self, search_string):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, rating, position, comment FROM bookmarks WHERE comment LIKE '%%%s%% ORDER BY name ASC, position ASC" % (search_string))
        return cursor.fetchall()

    def close(self):
        self.conn.close()

class PlayingController():
    
    def play_random_bookmark(self):
        return

    def play_first_file_bookmark(self):
        return

    def play_last_file_bookmark(self):
        return

    def play_next_bookmark(self):
        return

    def play_previous_bookmark(self):
        return

    def play_bookmark_by_id(self):
        return

    def play_most_recent_file(self):
        return

class BookmarkManager:
    def __init__(self):
        self.bookmarks = []
        self.bookmarks_unfiltered = []
        self.bookmarks_filtered = []
        self.db = BookmarkDatabase()
        self.moc = MocController()
        self.quit_event_loop = False

    def update_view(self, w=None, size=None, key=None, filter_string=None):
        pos = None
        try:
            pos = self.bookmarks_listbox.focus_position
        except:
            pass
        self.update_player_state()
        
        header = '{:<20s}{:s}'.format(
                'Name',
                'Directory')

        self.bookmarks.clear()
        self.content.clear()
        results = [[]]
        if filter_string is None:
            results = self.db.get_all()
        else:
            results = self.db.get_filtered(filter_string)

        for row in results:
            if row[2] is not None and row[2] > 0:
                remaining = MAX_RATING - row[2]                
                rating = "%s%s" % (row[2] * ' ★', remaining * ' ☆')
            else:
                rating =  MAX_RATING * ' ☆'
            line = '{:<5d}{:50s}{:5d}{:5s} {:s}'.format(row[0], os.path.basename(row[1]), row[3], rating, row[4])
            b = { 'id': row[0], "filename": row[1], "position": row[3], "rating": row[2], "comment": row[4] }
            self.bookmarks.append(b)
            self.content.append(urwid.AttrMap(urwid.SelectableIcon(line, 0), "normal", "selected"))

        if pos is not None and len(self.bookmarks) > 0:
            self.bookmarks_listbox.set_focus(pos)


    def create_button(self, text, handler=None):
        return urwid.AttrWrap(urwid.Button(text), "button", "button_selected")

    def init_ui(self):
    
        # Set up color scheme
        palette = [
            ('titlebar', 'light green', ''),
            ('hotkey', 'dark green,bold', ''),
            ('quit button', 'dark red', ''),
            ('headers', 'white,bold', ''),
            ('normal', 'white', ''),
            ('button', 'white', 'light blue'),
            ('button_selected', 'black', 'yellow'),
            ('selected', 'black', 'light green')]
    
        header_text = urwid.Text(u'MOCP Audio File Position Tagger')
        header = urwid.AttrMap(header_text, 'titlebar')
        self.content = urwid.SimpleListWalker([])
        self.bookmarks_listbox = urwid.ListBox(self.content)
    
        # footer menu
        menu = urwid.Text([
            u'(', ('hotkey', u'R'), u')eload bookmarks  ',
            u'(', ('hotkey', u'N'), u')ew  ',
            u'(', ('hotkey', u'E'), u')dit  ',
            u'(', ('hotkey', u'D'), u')elete selected  ',
            u'(', ('quit button', u'Q'), u')uit'
        ])
    
        self.bookmarks_linebox = urwid.LineBox(self.bookmarks_listbox, title="Bookmarks")
        #self.bookmarks_frame = urwid.Frame(header=self.make_hotkey_markup("_Bookmarks"), body=self.bookmarks_linebox)
        termsize = shutil.get_terminal_size((80, 30))
        self.edit_search = urwid.Edit(self.make_hotkey_markup("_Search: "))
        self.text_player_state = urwid.Text(["Player state: ", self.moc.get_player_state()])
        self.text_volume = urwid.Text('')
        self.header = urwid.Pile([
            header,
            self.text_player_state,
            self.edit_search,
            urwid.GridFlow([
                urwid.Text('Volume'),
                self.text_volume,
                urwid.Text('Rewind'),
                self.create_button('2m'),
                self.create_button("30s"),
                self.create_button("5s"),
                urwid.Text('Skip'),
                self.create_button("5s"),
                self.create_button("30s"),
                self.create_button("2m")
            ], 10, 1, 1, 'left'),
            urwid.GridFlow([
                urwid.Text('Jump to file'),
                self.create_button("Prev"),
                self.create_button("Next"),
                urwid.Text('Jump to bookm'),
                self.create_button("Prev"),
                self.create_button("Next"),
                self.create_button("Random")
            ], 14, 1, 1, 'left')
        ])
    
        # Assemble the widgets
        self.layout = urwid.Frame(header=self.header, body=self.bookmarks_linebox, footer=menu)

        self.top = SignalWrap(self.layout)
        self.top.listen('q', self.quit)
        self.top.listen('b', self.bookmark_playing_position)
        self.top.listen(' ', self.toggle_pause)
        self.top.listen('enter', self.play_selected_bookmark)
        self.top.listen('m', self.toggle_view_mode)
        self.top.listen('s', self.focus_search_edit)
        self.top.listen('p', self.play_previous_bookmark)
        self.top.listen('n', self.play_next_bookmark)
        self.top.listen(',', self.rewind_30_secs)
        self.top.listen('.', self.skip_30_secs)
        self.top.listen('<', self.rewind_120_secs)
        self.top.listen('>', self.skip_120_secs)
        self.top.listen('f8', self.focus_bookmarks_list)
        self.top.listen('tab', self.focus_bookmarks_list)
        #self.top.listen('e', self.export_cue_files)
        self.top.listen('e', self.edit_bookmark)
        self.top.listen('d', self.delete_bookmark)
        self.top.listen('r', self.update_view)
        self.top.listen('left', self.rewind_30_secs)
        self.top.listen('right', self.skip_30_secs)

        self.screen = urwid.raw_display.Screen()
        self.screen.register_palette(palette)
        self.update_view()
        self.update_volume()

    def export_cue_files(self, w, size, key):
        lb = urwid.ListBox(urwid.SimpleListWalker([
            urwid.Text("Export all bookmarks to cue sheets?"),
            urwid.Text(""),
            urwid.Text("A cue sheet will be created for every file with bookmarks.")
            ]))

        if not self.dialog(lb,
                [ ("OK", True), ("Cancel", False), ],
                title="Export Bookarks to CUE sheets?"):
            return
        files = []
        for b in self.bookmarks:
            if b['filename'] not in files:
                files.append(b['filename'])

        with open('foo', 'wt') as logfile:
            for f in files:
                with open('%s.cue' % f, 'wt') as cuefile:
                    logfile.write("%s\n" % f)
                    cuefile.write('FILE "%s" MP3\n' % os.path.basename(f))
                    track_id = 1
                    for row in self.db.get_bookmarks_by_file(f):
                        b = { 'id': row[0], "filename": row[1], "position": row[3], "rating": row[2], "comment": row[4] }
                        cuefile.write('  TRACK %02d AUDIO\n' % track_id)
                        pos = self.cue_format_seconds(b['position'])
                        cuefile.write('    INDEX 01 %s\n' % pos)
                        cuefile.write('    TITLE "%s"\n' % self.format_seconds(b['position']))
                        track_id += 1


    def cue_format_seconds(self, seconds):
        s = seconds % 60
        m = seconds / 60
        return "%02d:%02d:00" % (m, s)

    def format_seconds(self, seconds):
        s = seconds % 60
        m = seconds / 60 % 60
        h = seconds / 60 / 60
        return "%02dh:%02dm:%02ds" % (h, m, s)


    def focus_closest_bookmark_to_playing_pos(self):
        pass


    def delete_bookmark(self, w, size, key):
        pos = self.bookmarks_listbox.focus_position
        b = self.bookmarks[pos]
        if pos < len(self.bookmarks) - 1:
            new_pos = pos
        else:
            new_pos = pos - 1
            
        self.db.delete(b['id'])
        self.update_view()
        self.bookmarks_listbox.set_focus(new_pos)

    def focus_search_edit(self, w, size, key):
        self.layout.set_focus('header')

    def focus_bookmarks_list(self, w, size, key):
        search_string = self.edit_search.get_edit_text()
        if search_string is not None and search_string != "":
            self.update_view(filter_string=search_string)
        self.layout.set_focus('body')

    def toggle_view_mode(self, w, size, key):
        pass

    def update_player_state(self):
        self.text_player_state.set_text(["Player state: ", self.moc.get_player_state()])

    def update_volume(self):
        self.text_volume.set_text(self.moc.get_volume())

    def quit(self, w, size, key):

        self.screen.stop()
        self.quit_event_loop = True

    def toggle_pause(self, w, size, key):
        self.moc.toggle_pause()
        self.update_player_state()

    def play_bookmark(self, b):
        file_is_playing = self.moc.get_playing_file == b['filename']
        time.sleep(MOCP_DELAY)
        if not file_is_playing:
            file_is_playing = self.moc.play_file(b['filename'])
            time.sleep(MOCP_DELAY) 

        self.moc.jump_to_second(b['position'])
        time.sleep(MOCP_DELAY)

        self.update_player_state()

    def play_selected_bookmark(self, w, size, key):
        if len(self.bookmarks) == 0:
            return
        b = self.bookmarks[self.bookmarks_listbox.focus_position]
        self.play_bookmark(b)

    def play_previous_bookmark(self, w, size, key):
        current_pos = self.moc.get_playing_pos()
        time.sleep(MOCP_DELAY)
        current_file = self.moc.get_playing_file()
        time.sleep(MOCP_DELAY)
        row = self.db.get_previous_bookmark(current_file, current_pos)
        if not row is None:
            b = { 'id': row[0], "filename": row[1], "position": row[3], "rating": row[2], "comment": row[4] }
            self.play_bookmark(b)


    def play_next_bookmark(self, w, size, key):
        current_pos = self.moc.get_playing_pos()
        time.sleep(MOCP_DELAY)
        current_file = self.moc.get_playing_file()
        time.sleep(MOCP_DELAY)
        row = self.db.get_next_bookmark(current_file, current_pos)
        if not row is None:
            b = { 'id': row[0], "filename": row[1], "position": row[3], "rating": row[2], "comment": row[4] }
            self.play_bookmark(b)

    def rewind_30_secs(self, w, size, key):
        self.moc.rewind(30)
        self.update_player_state()

    def skip_30_secs(self, w, size, key):
        self.moc.skip(30)
        self.update_player_state()

    def rewind_120_secs(self, w, size, key):
        self.moc.rewind(120)
        self.update_player_state()

    def skip_120_secs(self, w, size, key):
        self.moc.skip(120)
        self.update_player_state()

    def write_selection_to_file(self):
        #self.directory = self.bookmarks[self.listbox.focus_position]['dir']
        pass

    def bookmark_playing_position(self, w, size, key):
        if self.moc.get_player_state() == "not running":
            # TODO: notify user
            return

        b = self.new_bookmark_dialog(self.moc.get_playing_file(), self.moc.get_playing_pos())
        if b == None:
            return
        rating = b['rating']
        if rating == None:
            rating = "NULL"
        comment = b['comment']
        if comment == None:
            comment = ""

        self.db.add(b['filename'], b['position'], min(MAX_RATING, rating), comment)
        self.update_view()
        #, bookmark['rating'], bookmark['comment'])

    def run(self):
        self.init_ui()
        self.screen.start()
        self.event_loop()

    def event_loop(self, toplevel=None):
        prev_quit_loop = self.quit_event_loop

        try:
            if toplevel is None:
                toplevel = self.top

            self.size = self.screen.get_cols_rows()

            self.quit_event_loop = False

            
            while not self.quit_event_loop:
                canvas = toplevel.render(self.size, focus=True)
                self.screen.draw_screen(self.size, canvas)
                keys = self.screen.get_input()

                for k in keys:
                    if k == "window resize":
                        self.size = self.screen.get_cols_rows()
                    elif k == 'esc':
                        self.quit_event_loop = [False]
                    else:
                        toplevel.keypress(self.size, k)

            return self.quit_event_loop
        finally:
            self.quit_event_loop = prev_quit_loop


    def dialog(self, content, buttons_and_results,
            title=None, bind_enter_esc=True, focus_buttons=False,
            extra_bindings=[]):
        class ResultSetter:
            def __init__(subself, res):  # noqa
                subself.res = res

            def __call__(subself, btn):  # noqa
                self.quit_event_loop = [subself.res]

        Attr = urwid.AttrMap  # noqa

        if bind_enter_esc:
            content = SignalWrap(content)

            def enter(w, size, key):
                self.quit_event_loop = [True]

            def esc(w, size, key):
                self.quit_event_loop = [False]

            content.listen("enter", enter)
            content.listen("esc", esc)

        button_widgets = []
        for btn_descr in buttons_and_results:
            if btn_descr is None:
                button_widgets.append(urwid.Text(""))
            else:
                btn_text, btn_result = btn_descr
                button_widgets.append(
                        Attr(urwid.Button(btn_text, ResultSetter(btn_result)),
                            "button", "focused button"))

        w = urwid.Columns([
            content,
            ("fixed", 15, urwid.ListBox(urwid.SimpleListWalker(button_widgets))),
            ], dividechars=1)

        if focus_buttons:
            w.set_focus_column(1)

        if title is not None:
            w = urwid.Pile([
                ("flow", urwid.AttrMap(
                    urwid.Text(title, align="center"),
                    "dialog title")),
                ("fixed", 1, urwid.SolidFill()),
                w])

        w = SignalWrap(w)
        for key, binding in extra_bindings:
            if isinstance(binding, str):
                w.listen(key, ResultSetter(binding))
            else:
                w.listen(key, binding)

        w = urwid.LineBox(w)

        w = urwid.Overlay(w, self.top,
                align="center",
                valign="middle",
                width=("relative", 75),
                height=("relative", 75),
                )
        w = Attr(w, "background")
        return self.event_loop(w)[0]

    def edit_bookmark(self, w, size, key):

        b = self.bookmarks[self.bookmarks_listbox.focus_position]
        b = self.edit_bookmark_dialog(b)
        if b == None:
            return

        rating = b['rating']
        if rating == None:
            rating = "NULL"
        comment = b['comment']
        if comment == None:
            comment = ""
        self.db.update(b['id'], min(MAX_RATING, rating), comment)
        self.update_view()


    def edit_bookmark_dialog(ui, b):
        edit_rating = urwid.IntEdit("Rating: ", b['rating'])
        edit_comment = urwid.Edit("Comment: ", b['comment'])

        lb_contents = ([edit_rating, edit_comment])
        lb = urwid.ListBox(urwid.SimpleListWalker(lb_contents))

        if ui.dialog(lb,         [
                    ("OK", True),
                    ("Cancel", False),
                ],
                title="Edit bookmark"):
            return { 'id': b['id'], "filename": b['filename'], "position": b['position'], "rating": edit_rating.value(), "comment": edit_comment.get_edit_text() }


    def new_bookmark_dialog(ui, filename, position):

        heading = urwid.Text("Save a bookmark for the current position\n")
        edit_rating = urwid.IntEdit("Rating: ")
        edit_comment = urwid.Edit("Comment: ")

        lb_contents = ([heading, edit_rating, edit_comment])
        lb = urwid.ListBox(urwid.SimpleListWalker(lb_contents))

        if ui.dialog(lb,         [
                    ("OK", True),
                    ("Cancel", False),
                ],
                title="Bookmark position"):
            return { "filename": filename, "position": position, "rating": edit_rating.value(), "comment": edit_comment.get_edit_text() }

    def make_hotkey_markup(self, s):
        import re
        match = re.match(r"^([^_]*)_(.)(.*)$", s)
        assert match is not None
    
        return [
                (None, match.group(1)),
                ("hotkey", match.group(2)),
                (None, match.group(3)),
                ]


app = BookmarkManager()
app.run()

#db.add("foo", 4, "a comment")
#db.add("foob", 4)
#db.add("fooc", comment="another comment")
#print(moc.get_playing_file())
#print(moc.get_playing_pos())
#moc.jump(40)
#moc.play_file("/media/Radio_X/RuFFM/2021-06-26_18-55_-_RadioX_-_RuFFM.mp3")
#for b in db.get_all():
#    print(b[1])
#
