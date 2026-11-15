package cos.premy.mines;

import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.AudioFormat;
import android.media.MediaPlayer;
import android.media.SoundPool;
import android.os.Build;
import android.util.Log;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.util.HashMap;
import java.util.HashSet;

/** Original foreground audio; static PCM attack starts without asynchronous preparation. */
@SuppressWarnings("deprecation")
public final class MineSound {
    private final Context context;
    private final AudioManager manager;
    private SoundPool pool;
    private MediaPlayer ambience;
    private AudioTrack blast;
    private byte[] blastPcm;
    private final HashMap<String,Integer> sounds=new HashMap<>();
    private final HashSet<Integer> ready=new HashSet<>();
    private boolean active,focused,enabled=true,released,blastStarted;
    private ExplosionState state;
    private AudioFocusRequest request;
    private final AudioManager.OnAudioFocusChangeListener listener=this::focusChanged;
    public MineSound(Context context){this.context=context;manager=(AudioManager)context.getSystemService(Context.AUDIO_SERVICE);}
    private void focusChanged(int change){
        focused=change==AudioManager.AUDIOFOCUS_GAIN;
        if(!focused){pausePlayers();return;}
        if(active&&enabled){
            if(ambience!=null)try{ambience.start();}catch(IllegalStateException ignored){}
            if(state!=null&&state.cell!=null&&state.animating()){blastStarted=false;startBlast(state);}
        }
    }
    public void resume(ExplosionState state){
        if(released||active)return;
        this.state=state;active=true;enabled=context.getSharedPreferences(GameStatus.SETTINGS,0).getBoolean("sound",true);
        if(!enabled)return;
        if(Build.VERSION.SDK_INT>=26){
            AudioAttributes attrs=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();
            request=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK).setAudioAttributes(attrs).setOnAudioFocusChangeListener(listener).build();
            focused=manager.requestAudioFocus(request)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED;
        }else focused=manager.requestAudioFocus(listener,AudioManager.STREAM_MUSIC,AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED;
        pool=new SoundPool(6,AudioManager.STREAM_MUSIC,0);
        pool.setOnLoadCompleteListener((p,id,status)->{if(status==0&&p==pool&&active)ready.add(id);});
        for(String name:new String[]{"select","open","flag","layer","start","turn","rescue","eliminated","win","lose"})try(AssetFileDescriptor f=context.getAssets().openFd("mine/"+name+".wav")){sounds.put(name,pool.load(f,1));}catch(Exception ex){Log.w("Mines3D","Effect unavailable",ex);}
        try{
            if(blastPcm==null)blastPcm=readPcm();
            blast=new AudioTrack(AudioManager.STREAM_MUSIC,48000,AudioFormat.CHANNEL_OUT_STEREO,AudioFormat.ENCODING_PCM_16BIT,blastPcm.length,AudioTrack.MODE_STATIC);
            if(blast.getState()==AudioTrack.STATE_UNINITIALIZED)throw new IllegalStateException("AudioTrack unavailable");
            blast.write(blastPcm,0,blastPcm.length);blast.setStereoVolume(.93f,.93f);
        }catch(Exception ex){if(blast!=null)blast.release();blast=null;Log.w("Mines3D","Blast audio unavailable",ex);}
        ambience=ambient();blastStarted=false;
        if(state.cell!=null&&state.animating())startBlast(state);
    }
    private byte[] readPcm()throws Exception{
        byte[] all;try(InputStream in=context.getAssets().open("mine/blast.wav");ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] b=new byte[16384];int n;while((n=in.read(b))!=-1)out.write(b,0,n);all=out.toByteArray();
        }
        for(int p=12;p+8<=all.length;){
            int n=(all[p+4]&255)|((all[p+5]&255)<<8)|((all[p+6]&255)<<16)|((all[p+7]&255)<<24);
            if(n<0||p+8L+n>all.length)throw new IllegalStateException("Invalid PCM data");
            if(all[p]=='d'&&all[p+1]=='a'&&all[p+2]=='t'&&all[p+3]=='a')return java.util.Arrays.copyOfRange(all,p+8,p+8+n);
            p+=8+n+(n&1);
        }
        throw new IllegalStateException("PCM chunk missing");
    }
    private MediaPlayer ambient(){
        MediaPlayer p=new MediaPlayer();
        try(AssetFileDescriptor f=context.getAssets().openFd("mine/ambience.ogg")){
            p.setAudioStreamType(AudioManager.STREAM_MUSIC);p.setDataSource(f.getFileDescriptor(),f.getStartOffset(),f.getLength());
            p.setLooping(true);p.setVolume(.30f,.30f);p.setOnErrorListener((m,w,e)->true);
            p.setOnPreparedListener(m->{if(active&&focused&&!released&&m==ambience)m.start();});p.prepareAsync();return p;
        }catch(Exception ex){p.release();Log.w("Mines3D","Ambience unavailable",ex);return null;}
    }
    public void play(String name){Integer id=sounds.get(name);if(active&&enabled&&focused&&pool!=null&&id!=null&&ready.contains(id))pool.play(id,.64f,.64f,1,0,1);}
    public void startBlast(ExplosionState state){
        if(!active||!enabled||!focused||blast==null||blastStarted||!state.animating())return;
        int frame=(int)(state.elapsed()*48);
        if(frame>=blastPcm.length/4)return;
        try{blast.pause();blast.setPlaybackHeadPosition(frame);blast.play();blastStarted=true;Log.i("Mines3D","BLAST_AUDIO_START phaseMs="+state.elapsed());}
        catch(IllegalStateException ex){Log.w("Mines3D","Blast playback rejected",ex);}
    }
    /** One static track bounds simultaneous volume; new server events replace, never stack. */
    public void networkBlast(ExplosionState state){this.state=state;blastStarted=false;startBlast(state);}
    private void pausePlayers(){
        if(ambience!=null)try{if(ambience.isPlaying())ambience.pause();}catch(IllegalStateException ignored){}
        if(blast!=null)try{blast.pause();}catch(IllegalStateException ignored){}
        if(pool!=null)pool.autoPause();
    }
    public void pause(){
        active=false;pausePlayers();
        if(ambience!=null){ambience.release();ambience=null;}
        if(blast!=null){blast.release();blast=null;}
        if(pool!=null){pool.release();pool=null;sounds.clear();ready.clear();}
        if(Build.VERSION.SDK_INT>=26&&request!=null)manager.abandonAudioFocusRequest(request);else manager.abandonAudioFocus(listener);
        focused=false;blastStarted=false;
    }
    public void release(){pause();released=true;blastPcm=null;}
}
