# Labirinto dos Processos 

## Componentes do grupo: ERIC FILIPE, JÉSSICA CAVALCANTE, JOÃO VITOR, JOSÉ VICTOR

### O que o código faz

É uma simulação onde vários processos (um por letra, de A a Z) andam por um
labirinto desenhado no terminal com `curses`, cada um procurando as 7
estrelas (`*`) espalhadas pelo mapa. Um processo só pode sair pela saída
depois de coletar todas as 7. O controle é todo pelo **teclado**, direto
no terminal: dá pra criar, pausar, retomar e matar processos sem sair da
tela do labirinto.

### Como os processos se movem

Cada processo é um `multiprocessing.Process` de verdade, rodando a função
`explorar_labirinto` de forma independente. O movimento é um passeio
aleatório: a cada passo, o processo olha os vizinhos livres (sem parede) e
escolhe um ao acaso - com uma regra simples pra não ficar "batendo" pra
frente e pra trás sem sair do lugar: se tiver mais de um caminho livre, ele
evita escolher a última posição de onde veio (`ultima_pos`).

A entrada fica em `(1, 0)` e a saída é a linha de baixo do labirinto
(linha 11), que no mapa é a única linha sem parede fechando a lateral
esquerda - ela fica aberta de propósito, formando um corredor de saída. A
condição de vitória confere isso:

```python
if y == 11 and x >= 45 and estrelas_coletadas == TOTAL_ESTRELAS:
```

Ou seja: só sai quem estiver na linha da saída, perto do lado direito, E já
tiver coletado as 7 estrelas. Conferi contando os `*` no mapa e realmente
são 7, batendo com `TOTAL_ESTRELAS = 7` - esse número está certo aqui
(diferente de uma versão anterior que eu vi, onde esse total estava errado).

### Pausar e matar processos com `Event`, não com sinais do SO

Essa é a maior diferença em relação a outras versões que eu vi desse
exercício: em vez de usar sinais reais do sistema operacional (`SIGSTOP`,
`SIGTERM`), esse código usa dois `multiprocessing.Event` por processo:

- `evento_pausa`: começa "setado" (`.set()`), ou seja, o processo roda
  normal. Pra pausar, o programa principal chama `.clear()`; o processo,
  no topo do laço, vê que o evento não está setado e fica parado em
  `evento_pausa.wait()` até alguém chamar `.set()` de novo.
- `evento_morte`: começa "não setado". Pra matar, o programa chama
  `.set()`; o processo confere isso logo no início de cada volta do laço
  e, se estiver setado, sai do `while` e termina sozinho.

Isso é uma pausa **cooperativa**: o processo só nota o pedido de pausa ou
morte quando chega de novo no topo do laço (ou logo depois de acordar do
`time.sleep`). Na prática funciona bem porque o laço é rápido, mas é
diferente de um `SIGSTOP` de verdade, que o sistema operacional aplica
instantaneamente, mesmo no meio de qualquer instrução. A vantagem desse
jeito com `Event` é que funciona em qualquer sistema operacional (inclusive
Windows, onde `SIGSTOP` nem existe).

### Sincronização e comunicação usadas

- **Queue** (`fila_posicoes`): cada processo manda pro pai sua posição
  atual e o que está fazendo ("Buscando...", "⭐ CONCLUÍDA!", "SAIU"...). O
  processo principal lê essa fila num laço e atualiza a tela.
- **Event** (`evento_pausa`, `evento_morte`): usados pra pausar/retomar/
  matar, como explicado acima - dois eventos por processo.
- **Lock** (`trava`): protege o trecho onde o processo conta que coletou
  uma estrela nova. Vale notar: do jeito que está escrito, cada processo
  guarda sua própria contagem (`estrelas_coletadas` e
  `posicoes_visitadas` são variáveis locais da função, não compartilhadas
  entre processos), então esse `with trava:` acaba não protegendo um
  recurso que outro processo também escreve - hoje ele não muda o
  resultado. Ele só faria diferença de verdade se `estrelas_coletadas`
  fosse trocado por um contador **compartilhado** (tipo um
  `multiprocessing.Value` ou um dict de `Manager`, como as estrelas
  coletadas globalmente por todos juntos).
- **Value compartilhado** (`velocidade_delay`, um `multiprocessing.Value`
  do tipo `'d'`, double): guarda a velocidade de todos os processos num
  único número compartilhado. Apertar `<` ou `>` muda esse valor, e como
  todo processo lê o mesmo `velocidade_delay.value` no `time.sleep()`,
  a velocidade de todo mundo muda junto, na hora.

### Controles pelo teclado

O programa usa `stdscr.nodelay(True)`, que faz `getch()` não travar
esperando o usuário digitar - ele só retorna `-1` se não tiver tecla
nenhuma apertada naquele instante. Isso permite o laço principal fazer
duas coisas ao mesmo tempo: checar se alguma tecla foi apertada E também
checar a fila de mensagens dos processos, tudo na mesma iteração, sem
travar a tela esperando.

| Tecla | Ação |
|-------|------|
| `+` | cria um novo processo (próxima letra livre, de A a Z) |
| letra minúscula (`a`, `b`...) | pausa ou retoma aquele processo (alterna) |
| letra MAIÚSCULA (`A`, `B`...) | mata aquele processo |
| `<` | deixa os processos mais lentos |
| `>` | deixa os processos mais rápidos |
| `ESC` | fecha o programa (e mata todos os processos que ainda estiverem rodando) |

### Como executar

```bash
python3 labirinto_eventos.py
```
