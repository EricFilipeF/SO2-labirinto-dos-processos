import curses
import multiprocessing
import time
import random
import string

# --- Desenho do labirinto (matriz de strings) ---
# As paredes são '#' e os caminhos são espaços. As estrelas são '*'.
MAPA_LABIRINTO = [
    "#################################################",
    "                #   *           #       *       #",
    "#####   #####   #   #########   #   #########   #",
    "# * #   #       #           #   #           #   #",
    "#   #   #   #############   #   #########   #   #",
    "#       #           *   #   #           #   #   #",
    "#########   #########   #   #########   #   #   #",
    "#           #           #           #   #       #",
    "#   #########   #################   #   #####   #",
    "#   #   *                   #   *   #       # * #",
    "#   #   #################   #   #########   #   #",
    "#                                                ",
    "#################################################"
]

SIMBOLOS_PROCESSOS = list(string.ascii_uppercase) # Letras de A a Z para identificar os processos
CORES_PROCESSOS = [curses.COLOR_BLUE, curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_YELLOW]
TOTAL_ESTRELAS = 7 # Quantas estrelas precisa pegar para poder sair

# --- O que cada processo filho faz rodando sozinho ---
def explorar_labirinto(id_processo, fila_posicoes, mapa, evento_pausa, evento_morte, trava, velocidade_delay, total_estrelas_global):
    pos_atual = (1, 0) # Todo processo começa na entrada do labirinto
    ultima_pos = None  
    direcoes = [(0, 1), (1, 0), (0, -1), (-1, 0)] # Cima, baixo, esquerda, direita
    
    estrelas_coletadas = 0
    posicoes_visitadas = set() # Pra não contar a mesma estrela duas vezes

    while True:
        # Se o SO mandou matar esse processo, ele sai do loop
        if evento_morte.is_set():
            break

        # Se o processo foi pausado pelo usuário, ele espera aqui até ser retomado
        if not evento_pausa.is_set():
            fila_posicoes.put((id_processo, pos_atual, "⏸️ SUSPENSO"))
            evento_pausa.wait() 
            fila_posicoes.put((id_processo, pos_atual, "▶️ RETOMADO"))

        if evento_morte.is_set():
            break

        # Avisa a tela o que o processo está fazendo
        tarefas_pendentes = TOTAL_ESTRELAS - estrelas_coletadas
        fila_posicoes.put((id_processo, pos_atual, f"Buscando... (Tarefas pendentes: {tarefas_pendentes})"))
        
        # Controla a velocidade do processo andando
        time.sleep(velocidade_delay.value) 
        
        y, x = pos_atual
        
        # Se achou uma estrela e ainda não pegou ela
        if mapa[y][x] == '*' and pos_atual not in posicoes_visitadas:
            estrelas_coletadas += 1
            posicoes_visitadas.add(pos_atual)
            
            # --- LOCK / REGIÃO CRÍTICA ---
            with trava: # Trava para proteger o incremento da variável compartilhada global
                total_estrelas_global.value += 1

            tarefas_pendentes = TOTAL_ESTRELAS - estrelas_coletadas
            fila_posicoes.put((id_processo, pos_atual, f"⭐ CONCLUÍDA! (Pendentes: {tarefas_pendentes})"))
            time.sleep(0.5) 
        
        # Condição para vencer: chegar na saída (última linha) com todas as estrelas
        if y == 11 and x >= 45 and estrelas_coletadas == TOTAL_ESTRELAS:
            fila_posicoes.put((id_processo, pos_atual, "SAIU"))
            break

        # Olha os caminhos que dá pra andar (sem bater na parede)
        caminhos_livres = []
        for dy, dx in direcoes:
            ny, nx = y + dy, x + dx
            if 0 <= ny < len(mapa) and 0 <= nx < len(mapa[0]) and mapa[ny][nx] != '#':
                caminhos_livres.append((ny, nx))

        # Evita ficar voltando direto pro lugar de onde veio (memória curta)
        if len(caminhos_livres) > 1 and ultima_pos in caminhos_livres:
            caminhos_livres.remove(ultima_pos)

        # Escolhe um caminho aleatório pra andar
        if caminhos_livres:
            nova_pos = random.choice(caminhos_livres)
            ultima_pos = pos_atual
            pos_atual = nova_pos

# --- Parte visual do terminal usando a biblioteca curses ---
def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    stdscr.nodelay(True) # Não trava a tela esperando o usuário digitar algo
    
    # Configura as cores dos processos
    for i in range(len(CORES_PROCESSOS)):
        curses.init_pair(i + 1, CORES_PROCESSOS[i], -1) 
    
    curses.init_pair(10, curses.COLOR_WHITE, -1)  # Cor da parede
    curses.init_pair(11, curses.COLOR_YELLOW, -1) # Cor da estrela
    curses.init_pair(12, curses.COLOR_GREEN, -1)  # Cor de sucesso/início
    curses.init_pair(13, curses.COLOR_RED, -1)    # Cor de erro/morte

    # Título do jogo e instruções no topo
    stdscr.addstr(0, 0, "LABIRINTO DOS PROCESSOS", curses.A_BOLD)
    stdscr.addstr(1, 0, "Múltiplos processos devem encontrar as 7 tarefas (estrelas) antes de sair.", curses.A_DIM)
    stdscr.addstr(2, 0, "[+] Criar | [a-z] Pausar/Retomar | [A-Z] Matar | [< ou >] Velocidade | [ESC] Sair", curses.A_DIM)

    # Função pra desenhar o labirinto na tela na primeira vez
    def desenhar_labirinto():
        for y, linha in enumerate(MAPA_LABIRINTO):
            for x, char in enumerate(linha):
                if char == '#':
                    stdscr.addstr(y + 3, x, "█", curses.color_pair(10))
                elif char == '*':
                    stdscr.addstr(y + 3, x, "★", curses.color_pair(11) | curses.A_BOLD)

    desenhar_labirinto()
    stdscr.refresh()

    painel_y = 3 + len(MAPA_LABIRINTO) + 1
    
    fila_posicoes = multiprocessing.Queue() # Fila para os filhos mandarem mensagens pro pai
    trava = multiprocessing.Lock()          # Lock para sincronizar a coleta
    velocidade_delay = multiprocessing.Value('d', 0.25) # Velocidade compartilhada
    total_estrelas_global = multiprocessing.Value('i', 0) # Variável compartilhada global
    
    processos = []
    eventos_pausa = []
    eventos_morte = [] 
    posicoes_anteriores = {}
    processos_encerrados = set()

    # Atualiza o texto do cabeçalho do painel incluindo o TOTAL GLOBAL DE ESTRELAS
    def atualizar_cabecalho_status():
        texto = f"STATUS DOS PROCESSOS - Velocidade: {velocidade_delay.value:.2f}s | ⭐ TOTAL GLOBAL: {total_estrelas_global.value}"
        stdscr.addstr(painel_y, 0, texto.ljust(80), curses.A_BOLD)

    atualizar_cabecalho_status()

    # Escreve o status de cada processo organizado em duas colunas na tela
    def escrever_status(idx, acao, cor=0, destaque=0):
        linha = painel_y + 1 + (idx // 2)
        coluna = 0 if idx % 2 == 0 else 55
        try:
            stdscr.addstr(linha, coluna, " " * 50) 
            texto = f"[{SIMBOLOS_PROCESSOS[idx]}] PID:{processos[idx].pid} {acao}"
            stdscr.addstr(linha, coluna, texto[:50], curses.color_pair(cor) | destaque)
        except curses.error:
            pass 

    # Função chamada quando a gente aperta '+' para criar um novo processo
    def criar_processo():
        idx = len(processos)
        if idx >= len(SIMBOLOS_PROCESSOS): 
            return 
        
        evt_pausa = multiprocessing.Event()
        evt_pausa.set() # Começa rodando normal
        eventos_pausa.append(evt_pausa)
        
        evt_morte = multiprocessing.Event()
        eventos_morte.append(evt_morte)
        
        # Cria o processo de fato usando a biblioteca multiprocessing
        p = multiprocessing.Process(
            target=explorar_labirinto, 
            args=(idx, fila_posicoes, MAPA_LABIRINTO, evt_pausa, evt_morte, trava, velocidade_delay, total_estrelas_global)
        )
        processos.append(p)
        p.start()
        posicoes_anteriores[idx] = (1, 0)
        escrever_status(idx, "INICIADO!", cor=12)

    # Loop principal que cuida do teclado e atualiza a tela
    rodando = True
    while rodando:
        tecla = stdscr.getch() # Lê qual tecla o usuário apertou
        
        if tecla == 27: # Tecla ESC fecha o programa
            rodando = False
            break
            
        elif tecla != -1:
            char = chr(tecla)
            
            # Aumentar ou diminuir velocidade
            if char == '>': 
                velocidade_delay.value = max(0.02, velocidade_delay.value - 0.05)
                atualizar_cabecalho_status()
                
            elif char == '<': 
                velocidade_delay.value = min(1.0, velocidade_delay.value + 0.05)
                atualizar_cabecalho_status()
                
            # Criar novo processo com '+'
            elif char == '+':
                criar_processo()
                
            # Controlar processos existentes pelas letras do teclado (A-Z)
            elif char.isalpha():
                idx = ord(char.upper()) - 65
                if idx < len(processos) and idx not in processos_encerrados:
                    if char.islower():
                        # Letra minúscula: pausa ou retoma o processo
                        if eventos_pausa[idx].is_set():
                            eventos_pausa[idx].clear() 
                        else:
                            eventos_pausa[idx].set()   
                    elif char.isupper():
                        # Letra maiúscula: mata o processo com segurança
                        eventos_morte[idx].set() 
                        eventos_pausa[idx].set() 
                        processos_encerrados.add(idx)
                        
                        y_ant, x_ant = posicoes_anteriores[idx]
                        try:
                            if MAPA_LABIRINTO[y_ant][x_ant] == '*':
                                stdscr.addstr(y_ant + 3, x_ant, "★", curses.color_pair(11) | curses.A_BOLD)
                            else:
                                stdscr.addstr(y_ant + 3, x_ant, ' ') 
                        except curses.error: pass
                        
                        escrever_status(idx, "MORTO pelo SO!", cor=13, destaque=curses.A_REVERSE)

        # Pega as atualizações que os filhos mandaram na fila
        try:
            id_proc, pos_atual, acao = fila_posicoes.get(timeout=0.05)
        except multiprocessing.queues.Empty:
            atualizar_cabecalho_status()
            continue
            
        # Atualiza a contagem exibida no cabeçalho toda vez que chegar algo na fila
        atualizar_cabecalho_status()
            
        if id_proc in processos_encerrados:
            continue
            
        y_visual, x_visual = pos_atual[0] + 3, pos_atual[1]
        y_ant, x_ant = posicoes_anteriores[id_proc]
        
        char_antigo = MAPA_LABIRINTO[y_ant][x_ant]
        
        try:
            # Limpa o rastro por onde o processo passou
            if char_antigo == '*':
                 stdscr.addstr(y_ant + 3, x_ant, "★", curses.color_pair(11) | curses.A_BOLD)
            else:
                 stdscr.addstr(y_ant + 3, x_ant, ' ') 
            
            # Desenha o processo na nova posição com sua cor específica
            stdscr.addstr(y_visual, x_visual, SIMBOLOS_PROCESSOS[id_proc], curses.color_pair((id_proc % 6) + 1) | curses.A_BOLD)
        except curses.error:
            pass 
            
        posicoes_anteriores[id_proc] = pos_atual
        escrever_status(id_proc, acao)

        # Se o processo ganhou e saiu do labirinto
        if acao == "SAIU":
            processos_encerrados.add(id_proc)
            escrever_status(id_proc, "ESCAPOU!", cor=12, destaque=curses.A_REVERSE)
            try:
                stdscr.addstr(y_visual, x_visual, ' ') 
            except curses.error: pass
            
        stdscr.refresh()

    # Quando sai do jogo, garante que todos os processos filhos ativos sejam encerrados
    for p in processos:
        if p.is_alive():
            p.terminate()
            p.join()

if __name__ == '__main__':
    curses.wrapper(main)