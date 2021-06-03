import numpy as np
import pandas as pd
import math
import re
import sqlite3

def create_sqlite_connector(db='UltimateGuitarTabs.db'):
    con = sqlite3.connect('../data/{}'.format(db))
    cur = con.cursor()
    return(con, cur)
        
def get_table(cur, tableName):
    cur.execute("SELECT * FROM "+tableName)
    
    return(cur.fetchall())

def exe_query(cur, query):
    try:
        cur.execute(query)
    except:
        print('Failed to execute query: {}'.format(query))

    return(cur.fetchall())

def fix_accidental(note, accidental):
    notes = np.asarray(['A', 'B', 'C', 'D', 'E', 'F', 'G'])

    note_idx = int(np.where(notes == note)[0])
    if accidental == '#':
        # Account for B# or E#
        if note == 'B':
            return('C', '')
        elif note == 'E':
            return('F', '')
        return(note,accidental)
    elif accidental == 'b':
        # Account for Cb or Fb
        if note == 'C':
            return('B', '')
        elif note == 'F':
            return('E', '')
        return(notes[note_idx - 1],'#')
    else:
        return(note, accidental)
            
        
def clean_chords(chords):
    """
    This function takes in a comma-separated string of 
    chords and cleans it by removing any base note variations, or
    other chord embelishments.  Diminished labels are kept as these
    are used in the chord progression table. The purpose of this
    is to clean the chords to match the labels within the chord
    progression table.
    
    returns:
        new_chords - array of newly cleaned chords to be tabulated
                        by the chord progression table
    """
    
    # Pattern grouping: 1=(chord pitch) 2=(base note) 3=(chord type) 4=(base note)
    pattern = "^([A-G]+)(\/[A-G]*[b#])*([(?m)|(?m\d)|(?b\d)|(?#\d)|(?maj\d)|\
    (?add\d)|(?sus\d)|(?aug)|(?aug\d)|(?dim)|(?dim\d)]*)(\/[A-G]*[b#])*"        
    prog = re.compile(pattern)

    pattern2 = "^([A-G])([b#])?(m$|m\d$)?(dim$|dim\d$)?"
    prog2 = re.compile(pattern2)

    chords = chords.split(',')

    new_chords = [""]*len(chords)
    for i in range(len(chords)):
        curr_chord = chords[i]
        groups = prog.findall(curr_chord)[0] 
        no_base = groups[0] + groups[2]
        no_num = re.sub(pattern="\d", repl="", string=no_base)

        groups = prog2.findall(no_num)[0]
        note,accidental = fix_accidental(groups[0], groups[1])
        new_chords[i] = note + accidental + groups[2] + groups[3]

    return(new_chords)


def get_key_tbls():
    """
    Helper function that reads in a chord progression table
    and creates a dictionary that maps chord names to their
    indices on the chord progression table. This dictionary
    will be used to tabulate a 'key table' to determine the
    key of a song.
    
    returns:
        Key_dict - Dictionary mapping chord names to indices
        Keys - array of keys that correspond to the order
                of the progression table
    """
    Key_tbl = pd.read_csv('../data/key_table.csv')
    Keys = list(Key_tbl.key)
    Tbl = np.asmatrix(Key_tbl.iloc[:,1:8])

    # Storing all possible chords 
    all_chords = []
    for i in range(Tbl.shape[0]):
        for j in np.asarray(Tbl[i])[0]:
            all_chords.append(j)
    all_chords = np.unique(all_chords)
    
    # Creating dict(key='chord', val='indices in progression tbl')
    Key_dict = {}
    for chord in all_chords:
        Key_dict[chord] = np.where(Tbl == chord)

    return(Key_dict, Keys)

def is_rel_min(comp_key, act_key):
    """
    Determines if the actual key marked indicated
    UltimateGuitarTabs.com is the relative minor
    of the actual key (i.e., Am(rel. minor) and C(actual))
    
    args:
        comp_key - Computed key
        act_key - UltimateGuitarTabs.com key
    returns:
        - True if it's relative minor, False otherwise
    """
    notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
    if str(act_key[-1]) != 'm': #If not minor, return 
        return(False)
    if len(comp_key) == 2:
        note, accidental = fix_accidental(comp_key[0],comp_key[1])
        comp_key = note + accidental
    comp_idx = np.where(np.asarray(notes) == comp_key)[0][0]
    rel_min_idx = comp_idx - 3
    if notes[rel_min_idx] + 'm' == act_key:
        return(True)

def compute_key(chords):
    """
    Computes the key of a song by analyzing
    the chords used within the song. A theoretical
    key matrix where each row specifies the types of chords
    that coincide with a key is used to tabulate
    the existing chords. The largest row sum is the
    computed key of the song. 
    
    args:
        Key_dict - Python dictionary containing all possible
                   chords and their indexes in the theoretical key matrix.
                   This is used to tabulate a matrix of zeros.
        Keys - List of possible keys corresponding to theoretical key matrix
        chords - String of chords separated by commas
                   
    returns:
        - The computed key
        - List of cleaned chords, only major or minor
    """

    Key_dict, Keys = get_key_tbls() # Grabbing key dictionary and keys

    chords = clean_chords(chords)
    count_mat = np.zeros((12,7)) # Matrix of zeros to tabulate chord occurences
    # Tabulating chords
    for chord in chords:
        count_mat[Key_dict[chord]] += 1
        
    computed_key = Keys[np.argmax(np.sum(count_mat, axis = 1))]
    return(computed_key, chords)
    
def transpose_C(chords, states, song_id):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    comp_key, chords = compute_key(chords)
    new_chords = [""]*len(chords) # Empty list for new chords
    if comp_key == 'C':
        for chord in chords:
            states.add(chord)
        return(states, \
               {'song_id' : song_id, \
                'orig_key': comp_key, \
                'trans_chords': chords})
    else:
        steps = np.where(np.asarray(notes) == comp_key)[0][0]
        for i in range(len(chords)):
            is_min = False
            is_dim = False
            curr_chord = chords[i]
            if curr_chord[-1] == 'm':
                if curr_chord[-3:len(curr_chord)] == 'dim':
                    is_dim = True
                    curr_chord = curr_chord[0:-3]
                else:
                    is_min = True
                    curr_chord = curr_chord[0:-1]
            
            chord_idx = np.where(np.asarray(notes) == curr_chord)[0][0]
            new_chord_idx = chord_idx - steps
            if is_min:
                new_chords[i] = notes[new_chord_idx] + 'm'
            elif is_dim:
                new_chords[i] = notes[new_chord_idx] + 'dim'
            else:
                new_chords[i] = notes[new_chord_idx]
            states.add(new_chords[i])
        return(states, \
               {'song_id' : song_id, \
                'orig_key': comp_key, \
                'trans_chords': new_chords})

def create_transition_mat(states, chords):
    states = list(states) # Ensuring states is a list 
    try:
        num_states = len(states)
        trans_mat = np.zeros((num_states, num_states))
        for i in range(1, len(chords)):
            curr_chord = chords[i - 1]
            curr_chord_idx = np.where(np.asarray(states) == curr_chord)[0][0]
            
            next_chord = chords[i]
            next_chord_idx = np.where(np.asarray(states) == next_chord)[0][0]
            trans_mat[curr_chord_idx, next_chord_idx] += 1

        row_sums = np.sum(trans_mat, axis = 1)
        trans_mat = trans_mat/row_sums
        return(np.nan_to_num(trans_mat))

    except:
        print("failed")

def compute_euclidean(mat1, mat2):
    # Computes euclidean distance between two
    # transition matrices
    # NOTE: Will produce runtime warning with division by zero
    mat_dif = mat1 - mat2
    return(math.sqrt(np.sum(np.multiply(mat_dif, mat_dif)))/mat1.shape[0])

def get_similar_songs(states, song_id, clean_chords, orig_chords):
    curr_song = clean_chords.loc[clean_chords['Id'] == song_id]
    chords = curr_song.iat[0, 2].split(',')#[0,2] As it's just one song and chords at idx 2
    tm = create_transition_mat(states,chords)
    dist = [0]*clean_chords.shape[0]
    for i in range(len(dist)):
        curr_tm = create_transition_mat(states,clean_chords['Chords'][i].split(','))
        dist[i] = compute_euclidean(tm, curr_tm)
        
    dist_ord = np.argsort(dist) # Sorting by distance ascending
    idxs = np.unique(list(orig_chords['Song'][dist_ord]), return_index=True)[1] # Indexes of unique entries
    sim_songs = orig_chords.iloc[dist_ord[sorted(idxs)]]

    # Creating ranking column
    sim_songs = sim_songs.reset_index()
    sim_songs['Rank'] = pd.Series(range(0,sim_songs.shape[0]))
    return(sim_songs.to_json(orient='records'))

def get_similar_songs_user_entry(states, chords, clean_chords, orig_chords):
    states, song = transpose_C(chords, states, 0)
    tm = create_transition_mat(states,song['trans_chords'])
    dist = [0]*clean_chords.shape[0]

    for i in range(len(dist)):
        curr_tm = create_transition_mat(states,clean_chords['Chords'][i].split(','))
        dist[i] = compute_euclidean(tm, curr_tm)
        
    dist_ord = np.argsort(dist) # Sorting by distance ascending
    idxs = np.unique(list(orig_chords['Song'][dist_ord]), return_index=True)[1] # Indexes of unique entries
    sim_songs = orig_chords.iloc[dist_ord[sorted(idxs)]]

    # Creating ranking column
    sim_songs = sim_songs.reset_index()
    sim_songs['Rank'] = pd.Series(range(1,sim_songs.shape[0]+1))
    return(sim_songs.to_json(orient='records'), song['orig_key'])

def get_song_links(song_id, chords, tabs_data):
    print('Pulling song link for ID {}'.format(song_id))
    curr_song = chords[(chords.Id == int(song_id))][['Song', 'Artist']]
    song_name = curr_song.iat[0, 0]
    artist = curr_song.iat[0, 1]

    tab_json = tabs_data[(tabs_data.Song == song_name) & (tabs_data.Artist == artist)][['Id', 'Tab_url']].to_json(orient='records')
    print('Returning link: {}'.format(tab_json))
    return(tab_json)
    # links = orig_chords['']

