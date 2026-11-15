package cos.premy.mines.online;
import android.content.Context;
import cos.premy.mines.MineTheme;

public final class OnlineText {
    public static final String[] MODES={"coop","hunt","puzzle","fault","daily","race","team"};
    public static String tr(Context c,String zh,String en){return MineTheme.tr(c,zh,en);}
    public static String mode(Context c,String id){switch(id){case "hunt":return tr(c,"猎雷淘汰赛","Mine hunters");case "puzzle":return tr(c,"团队无猜解谜","Team logic");case "fault":return tr(c,"断层合作","Fault expedition");case "daily":return tr(c,"每日团队挑战","Daily expedition");case "race":return tr(c,"同图竞速","Mirror race");case "team":return tr(c,"3v3 撤离赛","3v3 escape");default:return tr(c,"合作探矿","Co-op expedition");}}
    public static String role(Context c,String id){return "scout".equals(id)?tr(c,"侦察员 · 额外扫描1次","Scout · +1 scan"):"medic".equals(id)?tr(c,"救援员 · 额外救援1次","Medic · +1 rescue"):tr(c,"勘探员 · 通用操作","Explorer · standard tools");}
    public static String status(Context c,String id){switch(id){case "down":return tr(c,"待救援","Needs rescue");case "out":return tr(c,"观战","Spectating");default:return tr(c,"探索中","Exploring");}}
    public static String rules(Context c,String mode){
        if("hunt".equals(mode))return tr(c,"2–6人轮流行动，每回合15秒。开安全格公开线索；踩雷或确认错雷淘汰。正确确认3颗雷，或成为最后存活者获胜。雷已全部公开时按存活者猎雷数排名，同分并列。超时跳过，连续3次超时淘汰。疑似标记只是个人笔记。","2–6 players, 15 seconds per turn. Open a safe cell or confirm a mine. Opening a mine or a wrong confirmation eliminates you. First to 3 mines or last survivor wins. When all mines are exposed, survivors with the most claims tie for victory. Three consecutive timeouts eliminate you. Notes are private.");
        if("puzzle".equals(mode))return tr(c,"根据公开线索共同推理，正确标齐全部地雷且没有误旗获胜。提示先高亮相关格，再点击解释。旗帜不是推理真值。","Work from public clues. Flag every mine with no incorrect flags to win. Hint highlights the evidence first; tap again for the explanation. Player flags are not assumed true.");
        String common=tr(c,"打开最高层绿色入口到最底层橙色出口的安全路线。数字只数六邻格。全队安全值3、共享扫描2次；队友可消耗救援次数救起倒地者。开到矿石或矿工格自动完成支线。","Open a safe six-neighbour route from the top green entrance to the deepest amber exit. Team stability: 3; shared scans: 2. Teammates can spend rescues to revive a downed player. Opening ore or trapped-miner cells completes side objectives.");
        if("race".equals(mode))return tr(c,"每人独立操作相同初始矿井，率先打通撤离路线获胜。踩雷淘汰；只剩一人时获胜。对手操作不改变你的棋盘。","Everyone has an independent copy of the same mine. First to escape wins. A mine eliminates you; the last survivor also wins. Opponents cannot change your board.");
        if("team".equals(mode))common=tr(c,"六人分成两队，各队操作相同地图的独立副本，先撤离的队伍获胜。\n","Six players in two teams, each sharing its own copy of the same map. The first team to escape wins.\n")+common;
        if("daily".equals(mode))common+=tr(c,"\n按服务器北京时间、人数、难度及规则固定每日地图，同日重试保持同图。","\nDaily maps use server Beijing date, player count, difficulty and rules. Retries keep the same map.");
        return common;
    }
    public static String error(Context c,String code){switch(code){
        case "STATE_CHANGED":case "CELL_CHANGED":return tr(c,"局面已更新，请重新确认操作。","The board changed. Review your move.");
        case "NOT_YOUR_TURN":return tr(c,"还没轮到你，可以先观察和做笔记。","Not your turn. You can look around and make notes.");
        case "CANNOT_ACT":return tr(c,"当前只能观察；倒地后需要队友救援。","You cannot act now. Downed players need a rescue.");
        case "NO_SCANS":return tr(c,"本局扫描已用完。","No scans remain.");
        case "NO_RESCUES":return tr(c,"本队救援次数已用完。","No rescues remain.");
        case "SCAN_NEEDS_NUMBER":return tr(c,"请选择一个已打开的非零数字格。","Select an opened non-zero number.");
        case "NO_PROVABLE_HINT":return tr(c,"当前没有可证明的单步结论，请查看其他层。","No provable next step; examine other decks.");
        case "NOT_READY":return tr(c,"请等待所有参赛者在线并准备。","All players must be online and ready.");
        case "ROOM_CHANGED":return tr(c,"房间规则已改变，请重新查看并准备。","Room settings changed. Review and ready again.");
        case "ROOM_FULL":return tr(c,"六个参赛席已满，可在开局后观战。","All six player seats are full. Watch after start.");
        case "NOT_ENOUGH_PLAYERS":return tr(c,"人数不足，普通模式至少2人，3v3需要6人。","At least 2 players are required; 3v3 needs 6.");
        case "SESSION_EXPIRED":case "LOGIN_REQUIRED":return tr(c,"登录已过期，请重新登录。","Session expired. Sign in again.");
        case "ACCOUNT_DISABLED":return tr(c,"账号已暂停使用。","This account is disabled.");
        case "UPDATE_REQUIRED":return tr(c,"客户端版本或会话不兼容，请重新登录或更新。","Client or session is incompatible. Sign in again or update.");
        case "ROOM_CLOSED":case "ROOM_NOT_FOUND":return tr(c,"房间已关闭或邀请失效，请重新组队。","Room closed or invitation expired. Create or join another room.");
        default:return tr(c,"操作未完成：","Action not completed: ")+code;
    }}
}
