<div ref="{{ rootRef }}" style="position: relative; display: flex; flex-direction: column; height: 100vh; background: var(--surface); font-family: var(--font-ui); color: var(--tx2); overflow: hidden;">

  <header style="display: flex; align-items: center; gap: 4px; height: 46px; padding: 0 12px 0 14px; background: var(--bar); border-bottom: 1px solid rgba(var(--w), 0.07); flex-shrink: 0; z-index: 10;">
    <img src="./assets/arkalabs-logo-primary.svg" alt="arkalabs" style="width: 22px; height: 22px; display: block; margin-right: 9px;" />
    <span style="display: flex; align-items: baseline; gap: 8px; padding-right: 10px;">
      <span class="t-wordmark" style="font-size: 12px; color: var(--tx2);"><b>arka</b><i>labs</i></span>
      <span style="font-family: var(--font-sans); font-size: 16px; font-weight: 300; letter-spacing: -0.01em; color: var(--tx1);">Messenger<span style="font-weight: 900; color: var(--arka-red);">.</span></span>
    </span>
    <span style="color: var(--tx5); font-size: 13px;">/</span>
    <div title="{{ boxPath }}" style="display: flex; align-items: center; gap: 8px; height: 28px; padding: 0 9px; border-radius: 7px; cursor: default;" style-hover="background: rgba(var(--w), 0.05);">
      <span class="ic" style="width: 14px; height: 14px; color: var(--tx4); -webkit-mask-image: url('./assets/icons/inbox.svg'); mask-image: url('./assets/icons/inbox.svg');"></span>
      <span style="font-size: 13px; font-weight: 500; color: var(--tx1); white-space: nowrap;">{{ boxTitle }}</span>
      <span key="{{ newKey }}" class="pop" style="display: inline-flex; align-items: center; height: 17px; padding: 0 5px; border-radius: 4px; border: 1px solid rgba(217, 119, 6, 0.35); font-family: var(--font-mono); font-size: 8.5px; font-weight: 700; letter-spacing: 0.06em; color: var(--warn-tx); white-space: nowrap;">{{ newBadge }}</span>
    </div>
    <span style="flex: 1;"></span>
    <div onClick="{{ toggleLive }}" title="{{ liveTitle }}" style="display: flex; align-items: center; gap: 8px; height: 28px; padding: 0 10px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.1); cursor: {{ liveCursor }}; background: {{ liveBg }};" style-hover="background: rgba(var(--w), 0.05);">
      <span class="{{ livePulse }}" style="width: 6px; height: 6px; border-radius: 9999px; background: {{ liveDot }};"></span>
      <span style="font-size: 12px; color: var(--tx3); white-space: nowrap;">{{ liveLabel }}</span>
    </div>
    <span onClick="{{ toggleNotif }}" title="{{ notifTitle }}" class="ic" style="width: 16px; height: 16px; margin-left: 14px; color: {{ notifColor }}; cursor: pointer; -webkit-mask-image: url('{{ notifIcon }}'); mask-image: url('{{ notifIcon }}');"></span>
    <span onClick="{{ toggleLang }}" title="{{ langTitle }}" style="margin-left: 14px; font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--tx4); cursor: pointer;">{{ langLabel }}</span>
    <span onClick="{{ toggleTheme }}" title="{{ themeTitle }}" class="ic" style="width: 16px; height: 16px; margin-left: 14px; color: var(--tx4); cursor: pointer; -webkit-mask-image: url('{{ themeIcon }}'); mask-image: url('{{ themeIcon }}');"></span>
    <span title="{{ meTitle }}" style="width: 24px; height: 24px; border-radius: 9999px; border: 1px solid rgba(var(--w), 0.14); color: var(--tx3); font-family: var(--font-mono); font-size: 9px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-left: 14px;">OW</span>
  </header>

  <sc-if value="{{ hasIncidents }}" hint-placeholder-val="{{ false }}">
    <div style="display: flex; flex-direction: column; background: rgba(217, 119, 6, 0.09); border-bottom: 1px solid rgba(217, 119, 6, 0.26); flex-shrink: 0; z-index: 9;">
      <div onClick="{{ toggleIncidents }}" style="display: flex; align-items: center; gap: 9px; height: 27px; padding: 0 14px; cursor: pointer;" style-hover="background: rgba(217, 119, 6, 0.07);">
        <span class="ic" style="width: 12px; height: 12px; color: var(--warn-tx); -webkit-mask-image: url('./assets/icons/triangle-alert.svg'); mask-image: url('./assets/icons/triangle-alert.svg');"></span>
        <span style="font-size: 11.5px; font-weight: 600; color: var(--warn-tx); white-space: nowrap;">{{ incidentCount }}</span>
        <span style="flex: 1; min-width: 0; font-size: 11.5px; color: var(--warn-tx); opacity: 0.85; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ incidentPeek }}</span>
        <span style="font-size: 11.5px; color: var(--warn-tx); white-space: nowrap;">{{ incidentToggle }}</span>
        <span class="ic" style="width: 12px; height: 12px; color: var(--warn-tx); transform: {{ incidentCaret }}; transition: transform 170ms cubic-bezier(0.16, 1, 0.3, 1); -webkit-mask-image: url('./assets/icons/chevron-down.svg'); mask-image: url('./assets/icons/chevron-down.svg');"></span>
      </div>
      <sc-if value="{{ incidentsOpen }}" hint-placeholder-val="{{ false }}">
        <div class="fade-in" style="display: flex; flex-direction: column;">
          <sc-for list="{{ incidents }}" as="i" hint-placeholder-count="2">
            <div class="drop" style="display: flex; align-items: center; gap: 10px; padding: 7px 14px 7px 35px; border-top: 1px solid rgba(217, 119, 6, 0.14);">
              <span class="ic" style="width: 13px; height: 13px; color: var(--warn-tx); -webkit-mask-image: url('{{ i.icon }}'); mask-image: url('{{ i.icon }}');"></span>
              <span style="flex: 1; min-width: 0; font-size: 12px; color: var(--warn-tx); line-height: 1.4; text-wrap: pretty;">{{ i.text }}</span>
              <span onClick="{{ i.act }}" style="display: inline-flex; align-items: center; height: 22px; padding: 0 9px; border-radius: 6px; border: 1px solid rgba(217, 119, 6, 0.4); font-size: 11.5px; color: var(--warn-tx); cursor: pointer; white-space: nowrap;" style-hover="background: rgba(217, 119, 6, 0.12);">{{ i.cta }}</span>
              <sc-if value="{{ i.canHide }}" hint-placeholder-val="{{ true }}">
                <span onClick="{{ i.hide }}" title="Masquer" class="ic" style="width: 12px; height: 12px; color: var(--warn-tx); cursor: pointer; opacity: 0.7; -webkit-mask-image: url('./assets/icons/x.svg'); mask-image: url('./assets/icons/x.svg');"></span>
              </sc-if>
            </div>
          </sc-for>
        </div>
      </sc-if>
    </div>
  </sc-if>

  <div style="display: flex; flex: 1; min-height: 0;">

    <aside style="width: 272px; flex-shrink: 0; box-sizing: border-box; background: var(--bar); border-right: 1px solid rgba(var(--w), 0.07); display: flex; flex-direction: column; overflow-y: auto;">

      <div style="padding: 12px 10px 12px; display: flex; flex-direction: column; gap: 2px;">
        <sc-for list="{{ boxes }}" as="b" hint-placeholder-count="4">
          <div onClick="{{ b.pick }}" style="display: flex; align-items: center; gap: 10px; height: 33px; padding: 0 9px; border-radius: 7px; cursor: pointer; background: {{ b.bg }}; transition: background 140ms ease;" style-hover="background: rgba(var(--w), 0.05);">
            <span class="ic" style="width: 15px; height: 15px; color: {{ b.color }}; -webkit-mask-image: url('{{ b.icon }}'); mask-image: url('{{ b.icon }}');"></span>
            <span style="flex: 1; min-width: 0; font-size: 13px; color: {{ b.color }}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ b.label }}</span>
            <span key="{{ b.count }}" class="pop" style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5);">{{ b.count }}</span>
          </div>
        </sc-for>
      </div>

      <div style="border-top: 1px solid rgba(var(--w), 0.06); padding: 13px 10px 14px; display: flex; flex-direction: column; gap: 3px;">
        <div style="display: flex; align-items: center; padding: 0 9px 9px;">
          <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--tx5);">Tes agents</span>
          <span style="flex: 1;"></span>
          <span onClick="{{ pickAllProjects }}" style="font-size: 11px; color: {{ allProjColor }}; cursor: pointer;">Tous</span>
        </div>

        <sc-for list="{{ groups }}" as="g" hint-placeholder-count="3">
          <div style="display: flex; flex-direction: column; gap: 2px; padding-bottom: 6px;">
            <div onClick="{{ g.toggle }}" style="display: flex; align-items: center; gap: 8px; height: 29px; padding: 0 9px; border-radius: 7px; cursor: pointer; background: {{ g.bg }}; transition: background 140ms ease;" style-hover="background: rgba(var(--w), 0.05);">
              <span class="ic" style="width: 12px; height: 12px; color: var(--tx5); transform: {{ g.caret }}; transition: transform 170ms cubic-bezier(0.16, 1, 0.3, 1); -webkit-mask-image: url('./assets/icons/chevron-right.svg'); mask-image: url('./assets/icons/chevron-right.svg');"></span>
              <span onClick="{{ g.pick }}" style="display: inline-flex; align-items: center; height: 18px; padding: 0 7px; border-radius: 5px; border: 1px solid {{ g.tint }}; font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: {{ g.tint }}; white-space: nowrap;">{{ g.name }}</span>
              <span style="flex: 1;"></span>
              <sc-if value="{{ g.hasNew }}" hint-placeholder-val="{{ true }}">
                <span title="{{ g.newTitle }}" class="pulse" style="width: 6px; height: 6px; border-radius: 9999px; background: var(--warn-tx);"></span>
              </sc-if>
              <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5);">{{ g.count }}</span>
            </div>

            <sc-if value="{{ g.open }}" hint-placeholder-val="{{ true }}">
              <div class="fade-in" style="display: flex; flex-direction: column; gap: 3px; padding: 3px 0 0 6px;">
                <sc-for list="{{ g.agents }}" as="a" hint-placeholder-count="4">
                  <div onClick="{{ a.open }}" title="{{ a.tip }}" style="display: flex; flex-direction: column; gap: 3px; padding: 7px 9px 8px; border-radius: 7px; border: 1px solid {{ a.border }}; background: {{ a.bg }}; cursor: pointer; transition: background 140ms ease, border-color 140ms ease;" style-hover="background: rgba(var(--w), 0.05);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span class="{{ a.pulse }}" style="width: 6px; height: 6px; border-radius: 9999px; background: {{ a.dot }}; flex-shrink: 0;"></span>
                      <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 11.5px; color: {{ a.color }}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ a.name }}</span>
                      <span onClick="{{ a.more }}" title="Options de ce compte" class="ic" style="width: 13px; height: 13px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/ellipsis.svg'); mask-image: url('./assets/icons/ellipsis.svg');"></span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 7px; padding-left: 14px;">
                      <span style="font-size: 10.5px; color: var(--tx5); white-space: nowrap;">{{ a.last }}</span>
                      <sc-if value="{{ a.waiting }}" hint-placeholder-val="{{ true }}">
                        <span style="font-size: 10.5px; color: var(--warn-tx); white-space: nowrap;">{{ a.waitLabel }}</span>
                      </sc-if>
                    </div>
                  </div>
                </sc-for>
                <sc-if value="{{ g.empty }}" hint-placeholder-val="{{ false }}">
                  <span style="font-size: 11.5px; color: var(--tx4); line-height: 1.5; padding: 4px 9px 6px;">Aucun agent encore — copie l'invite et colle-la à ton agent.</span>
                </sc-if>
              </div>
            </sc-if>
          </div>
        </sc-for>

        <sc-if value="{{ hasInactive }}" hint-placeholder-val="{{ false }}">
          <div style="display: flex; flex-direction: column; gap: 2px; padding-top: 2px;">
            <div onClick="{{ toggleInactive }}" style="display: flex; align-items: center; gap: 8px; height: 25px; padding: 0 9px; border-radius: 7px; cursor: pointer;" style-hover="background: rgba(var(--w), 0.05);">
              <span class="ic" style="width: 11px; height: 11px; color: var(--tx5); transform: {{ inactiveCaret }}; transition: transform 170ms cubic-bezier(0.16, 1, 0.3, 1); -webkit-mask-image: url('./assets/icons/chevron-right.svg'); mask-image: url('./assets/icons/chevron-right.svg');"></span>
              <span style="font-size: 11px; color: var(--tx5); white-space: nowrap;">{{ inactiveTitle }}</span>
            </div>
            <sc-if value="{{ inactiveOpen }}" hint-placeholder-val="{{ false }}">
              <div class="fade-in" style="display: flex; flex-direction: column; gap: 3px; padding: 3px 0 0 6px;">
                <span style="font-size: 10.5px; color: var(--tx5); padding: 0 9px 2px;">Leur historique reste dans la boîte.</span>
                <sc-for list="{{ inactive }}" as="off" hint-placeholder-count="1">
                  <div title="{{ off.tip }}" style="display: flex; flex-direction: column; gap: 3px; padding: 7px 9px 8px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.07);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 11px; color: var(--tx4); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ off.name }}</span>
                      <button type="button" onClick="{{ off.reactivate }}" style="height: 22px; padding: 0 8px; border-radius: 6px; border: 1px solid rgba(var(--w), 0.14); background: transparent; font-family: var(--font-ui); font-size: 11px; color: var(--tx2); cursor: pointer; white-space: nowrap;">Réactiver</button>
                    </div>
                    <span style="font-size: 10.5px; color: var(--tx5); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ off.post }}</span>
                    <sc-if value="{{ off.hasNotice }}" hint-placeholder-val="{{ false }}">
                      <span role="alert" style="font-size: 11px; color: var(--fail-tx); line-height: 1.45;">{{ off.notice }}</span>
                    </sc-if>
                  </div>
                </sc-for>
              </div>
            </sc-if>
          </div>
        </sc-if>
      </div>

      <div style="border-top: 1px solid rgba(var(--w), 0.06); padding: 13px 10px 14px; display: flex; flex-direction: column; gap: 4px;">
        <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--tx5); padding: 0 9px 8px;">Mise en place</span>
        <sc-for list="{{ ctas }}" as="c" hint-placeholder-count="3">
          <div onClick="{{ c.act }}" style="display: flex; align-items: center; gap: 10px; height: 34px; padding: 0 9px; border-radius: 7px; border: 1px solid {{ c.border }}; cursor: pointer; background: {{ c.bg }}; transition: background 140ms ease;" style-hover="background: rgba(var(--w), 0.06);">
            <span class="ic" style="width: 15px; height: 15px; color: {{ c.color }}; -webkit-mask-image: url('{{ c.icon }}'); mask-image: url('{{ c.icon }}');"></span>
            <span style="flex: 1; min-width: 0; font-size: 12.5px; color: {{ c.color }}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ c.label }}</span>
            <sc-if value="{{ c.todo }}" hint-placeholder-val="{{ true }}">
              <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.06em; color: var(--warn-tx);">À FAIRE</span>
            </sc-if>
          </div>
        </sc-for>
      </div>

      <div style="border-top: 1px solid rgba(var(--w), 0.06); padding: 13px 18px 16px; display: flex; flex-direction: column; gap: 9px;">
        <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--tx5);">Cet ordinateur</span>
        <span style="font-size: 12px; color: var(--tx3); line-height: 1.5;">{{ boxDescription }}</span>
        <span title="{{ boxPath }}" style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ boxPath }}</span>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="ic" style="width: 13px; height: 13px; color: var(--pass-tx); -webkit-mask-image: url('./assets/icons/check.svg'); mask-image: url('./assets/icons/check.svg');"></span>
          <span title="Ces outils lisent et écrivent la boîte tout seuls" style="flex: 1; min-width: 0; font-size: 11.5px; color: var(--tx4); line-height: 1.45;">{{ toolsLabel }}</span>
        </div>
        <div onClick="{{ openPoste }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 27px; padding: 0 10px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.12); cursor: pointer;" style-hover="background: rgba(var(--w), 0.05);">
          <span class="ic" style="width: 13px; height: 13px; color: var(--tx4); -webkit-mask-image: url('./assets/icons/settings-2.svg'); mask-image: url('./assets/icons/settings-2.svg');"></span>
          <span style="font-size: 12px; color: var(--tx2);">Réglages de cet ordinateur</span>
        </div>
      </div>

      <div style="border-top: 1px solid rgba(var(--w), 0.06); padding: 13px 18px 20px; display: flex; flex-direction: column; gap: 8px;">
        <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--tx5);">Relève du courrier</span>
        <span style="font-size: 11.5px; color: var(--tx4); line-height: 1.5;">La remise dépend du fournisseur et de la session. Chaque agent relève aussi à l’ouverture et quand son humain lui parle.</span>
        <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5);">{{ lastSweep }}</span>
      </div>
    </aside>

    <main style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--zone);">

      <div style="display: flex; align-items: center; gap: 8px; height: 42px; padding: 0 14px; background: var(--head); border-bottom: 1px solid rgba(var(--w), 0.07); flex-shrink: 0;">
        <sc-for list="{{ chips }}" as="c" hint-placeholder-count="4">
          <div onClick="{{ c.pick }}" style="display: flex; align-items: center; gap: 7px; height: 25px; padding: 0 9px; border-radius: 6px; border: 1px solid {{ c.border }}; background: {{ c.bg }}; cursor: pointer; transition: background 140ms ease, border-color 140ms ease;" style-hover="background: rgba(var(--w), 0.06);">
            <span style="font-size: 12px; color: {{ c.color }}; white-space: nowrap;">{{ c.label }}</span>
            <span key="{{ c.count }}" class="pop" style="font-family: var(--font-mono); font-size: 9.5px; color: var(--tx5);">{{ c.count }}</span>
          </div>
        </sc-for>
        <span style="flex: 1;"></span>
        <div style="display: flex; align-items: center; gap: 8px; height: 26px; padding: 0 9px; border-radius: 6px; border: 1px solid rgba(var(--w), 0.1);">
          <span class="ic" style="width: 13px; height: 13px; color: var(--tx4); -webkit-mask-image: url('./assets/icons/search.svg'); mask-image: url('./assets/icons/search.svg');"></span>
          <input value="{{ query }}" onChange="{{ onQuery }}" placeholder="Objet, id, pièce jointe" aria-label="Rechercher dans la boîte" style="width: 210px; border: none; outline: none; background: transparent; font-family: var(--font-ui); font-size: 12px; color: var(--tx2);" />
        </div>
      </div>

      <sc-if value="{{ hasApprovals }}" hint-placeholder-val="{{ false }}">
        <section aria-label="Demandes de validation" style="display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; border-bottom: 1px solid rgba(var(--w), 0.07); background: var(--head); flex-shrink: 0; max-height: 230px; overflow-y: auto;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="ic" style="width: 13px; height: 13px; color: var(--warn-tx); -webkit-mask-image: url('./assets/icons/hand.svg'); mask-image: url('./assets/icons/hand.svg');"></span>
            <span style="font-size: 12px; font-weight: 600; color: var(--tx1);">Ce qu’on te demande</span>
            <span style="font-family: var(--font-mono); font-size: 10px; color: var(--warn-tx);">{{ approvalCount }} en attente</span>
          </div>
          <sc-for list="{{ approvalItems }}" as="request" hint-placeholder-count="1">
            <article ref="{{ request.reveal }}" style="display: flex; align-items: flex-start; gap: 12px; padding: 11px 12px; border: 1px solid {{ request.border }}; border-radius: 8px; background: var(--zone);">
              <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px;">
                <span style="font-size: 13px; font-weight: 600; color: var(--tx1);">{{ request.gesture }}</span>
                <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx4);">{{ request.from }} · {{ request.scope }}</span>
                <span style="font-size: 11.5px; color: var(--tx3);">Maintenant : {{ request.whyNow }}</span>
                <span style="font-size: 11.5px; color: var(--tx3);">{{ request.result }}</span>
                <span style="font-size: 11.5px; color: var(--tx4);">Retour : {{ request.reversible }} · Si refus : {{ request.ifRefused }}</span>
              </span>
              <span style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; color: {{ request.stateColor }};">{{ request.state }}</span>
                <sc-if value="{{ request.pending }}" hint-placeholder-val="{{ true }}">
                  <span style="display: flex; align-items: center; gap: 6px;">
                    <sc-for list="{{ request.actions }}" as="action" hint-placeholder-count="3">
                      <button onClick="{{ action.act }}" type="button" style="height: 28px; padding: 0 10px; border-radius: 6px; border: 1px solid rgba(var(--w), 0.14); background: transparent; font-family: var(--font-ui); font-size: 11.5px; color: {{ action.color }}; cursor: pointer;">{{ action.label }}</button>
                    </sc-for>
                  </span>
                </sc-if>
              </span>
            </article>
          </sc-for>
        </section>
      </sc-if>

      <div style="padding: 15px 16px 12px; border-bottom: 1px solid rgba(var(--w), 0.06); flex-shrink: 0;">
        <div style="display: flex; align-items: baseline; gap: 10px; padding-bottom: 12px;">
          <span style="font-size: 12px; font-weight: 600; color: var(--tx1);">{{ trafficTitle }}</span>
          <span style="font-size: 11px; color: var(--tx4);">{{ dayCaption }}</span>
          <span style="flex: 1;"></span>
          <span style="font-family: var(--font-mono); font-size: 9.5px; color: var(--tx5);">00:00 → 24:00 · heure de Paris</span>
        </div>
        <sc-if value="{{ loading }}" hint-placeholder-val="{{ true }}">
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <sc-for list="{{ five }}" as="n" hint-placeholder-count="5">
              <div class="sk" style="height: 14px;"></div>
            </sc-for>
          </div>
        </sc-if>
        <sc-if value="{{ ready }}" hint-placeholder-val="{{ false }}">
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <sc-for list="{{ lanes }}" as="l" hint-placeholder-count="5">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span onClick="{{ l.pick }}" title="{{ l.id }}" style="width: 148px; font-family: var(--font-mono); font-size: 10px; color: {{ l.nameColor }}; text-align: right; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer;">{{ l.short }}</span>
                <div style="position: relative; flex: 1; height: 18px; border-bottom: 1px solid rgba(var(--w), 0.05);">
                  <sc-for list="{{ l.dots }}" as="d" hint-placeholder-count="4">
                    <span onClick="{{ d.pick }}" title="{{ d.title }}" class="dot-in" style="position: absolute; top: 5px; left: {{ d.left }}; width: {{ d.size }}; height: {{ d.size }}; margin-left: -4px; border-radius: 9999px; background: {{ d.bg }}; border: 1px solid {{ d.ring }}; cursor: pointer; animation-delay: {{ d.delay }}; transition: transform 140ms ease;" style-hover="transform: scale(1.7);"></span>
                  </sc-for>
                </div>
              </div>
            </sc-for>
            <sc-if value="{{ noTraffic }}" hint-placeholder-val="{{ false }}">
              <span style="font-size: 12px; color: var(--tx4); padding: 6px 0 2px;">Aucun trafic ce jour-là.</span>
            </sc-if>
            <div style="display: flex; align-items: center; gap: 10px; padding-top: 3px;">
              <span style="width: 148px; flex-shrink: 0;"></span>
              <div style="position: relative; flex: 1; height: 12px;">
                <sc-for list="{{ ticks }}" as="t" hint-placeholder-count="5">
                  <span style="position: absolute; left: {{ t.left }}; transform: {{ t.shift }}; font-family: var(--font-mono); font-size: 9px; color: var(--tx5); white-space: nowrap;">{{ t.label }}</span>
                </sc-for>
                <span class="sweep" style="position: absolute; top: {{ nowTop }}; left: {{ nowLeft }}; width: 1px; height: {{ nowHeight }}; background: var(--tx3);"></span>
              </div>
            </div>
          </div>
        </sc-if>
      </div>

      <div style="display: flex; flex: 1; min-height: 0;">

        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; border-right: 1px solid rgba(var(--w), 0.07);">
          <div style="display: flex; align-items: center; gap: 10px; height: 30px; padding: 0 16px; background: var(--head); border-bottom: 1px solid rgba(var(--w), 0.07); flex-shrink: 0;">
            <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--tx5);">{{ listTitle }}</span>
            <span style="flex: 1;"></span>
            <sc-for list="{{ modes }}" as="v" hint-placeholder-count="2">
              <span onClick="{{ v.pick }}" style="display: inline-flex; align-items: center; height: 20px; padding: 0 8px; border-radius: 5px; border: 1px solid {{ v.border }}; background: {{ v.bg }}; font-size: 11px; color: {{ v.color }}; cursor: pointer; white-space: nowrap; transition: background 140ms ease;" style-hover="background: rgba(var(--w), 0.06);">{{ v.label }}</span>
            </sc-for>
            <span style="font-family: var(--font-mono); font-size: 9.5px; color: var(--tx5); padding-left: 4px;">{{ listCaption }}</span>
          </div>
          <div style="flex: 1; overflow-y: auto; min-height: 0;">
            <sc-if value="{{ loading }}" hint-placeholder-val="{{ true }}">
              <div style="display: flex; flex-direction: column; padding: 11px 16px; gap: 15px;">
                <sc-for list="{{ eight }}" as="n" hint-placeholder-count="8">
                  <div style="display: flex; flex-direction: column; gap: 6px;">
                    <div class="sk" style="height: 10px; width: 34%;"></div>
                    <div class="sk" style="height: 12px; width: 78%;"></div>
                  </div>
                </sc-for>
              </div>
            </sc-if>
            <sc-if value="{{ threadView }}" hint-placeholder-val="{{ false }}">
              <div style="display: flex; flex-direction: column;">
                <sc-for list="{{ threads }}" as="t" hint-placeholder-count="8">
                  <div class="{{ t.anim }}" style="display: flex; flex-direction: column; border-bottom: 1px solid rgba(var(--w), 0.06); border-left: 2px solid {{ t.mark }}; background: {{ t.bg }}; animation-delay: {{ t.delay }};">
                    <div onClick="{{ t.toggle }}" style="display: flex; align-items: flex-start; gap: 10px; padding: 11px 16px 12px; cursor: pointer;" style-hover="background: rgba(var(--w), 0.04);">
                      <span class="ic" style="width: 13px; height: 13px; margin-top: 3px; color: var(--tx5); transform: {{ t.caret }}; transition: transform 170ms cubic-bezier(0.16, 1, 0.3, 1); -webkit-mask-image: url('./assets/icons/chevron-right.svg'); mask-image: url('./assets/icons/chevron-right.svg');"></span>
                      <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px;">
                        <span style="font-size: 13px; color: {{ t.titleColor }}; font-weight: {{ t.weight }}; line-height: 1.4; text-wrap: pretty;">{{ t.title }}</span>
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                          <span style="font-family: var(--font-mono); font-size: 10.5px; color: var(--tx4); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 320px;">{{ t.people }}</span>
                          <span style="color: var(--tx5); font-size: 10px;">·</span>
                          <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5); white-space: nowrap;">{{ t.span }}</span>
                          <sc-for list="{{ t.tags }}" as="p" hint-placeholder-count="1">
                            <span title="{{ p.title }}" style="display: inline-flex; align-items: center; height: 16px; padding: 0 6px; border-radius: 4px; border: 1px solid {{ p.tint }}; font-family: var(--font-mono); font-size: 9px; color: {{ p.tint }}; white-space: nowrap;">{{ p.name }}</span>
                          </sc-for>
                          <sc-if value="{{ t.stalled }}" hint-placeholder-val="{{ true }}">
                            <span title="Ce fil n'a aucune réponse" style="display: inline-flex; align-items: center; gap: 5px; height: 17px; padding: 0 7px; border-radius: 5px; border: 1px solid rgba(217, 119, 6, 0.32); background: rgba(217, 119, 6, 0.10);">
                              <span class="ic" style="width: 10px; height: 10px; color: var(--warn-tx); -webkit-mask-image: url('./assets/icons/message-circle-dashed.svg'); mask-image: url('./assets/icons/message-circle-dashed.svg');"></span>
                              <span style="font-size: 10.5px; color: var(--warn-tx); white-space: nowrap;">sans réponse</span>
                            </span>
                          </sc-if>
                          <sc-if value="{{ t.forMe }}" hint-placeholder-val="{{ true }}">
                            <span style="display: inline-flex; align-items: center; gap: 5px; height: 17px; padding: 0 7px; border-radius: 5px; border: 1px solid {{ t.roleBorder }}; background: {{ t.roleBg }};">
                              <span class="ic" style="width: 10px; height: 10px; color: {{ t.roleColor }}; -webkit-mask-image: url('{{ t.roleIcon }}'); mask-image: url('{{ t.roleIcon }}');"></span>
                              <span style="font-size: 10.5px; color: {{ t.roleColor }}; white-space: nowrap;">{{ t.roleLabel }}</span>
                            </span>
                          </sc-if>
                        </div>
                      </span>
                      <span style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px; flex-shrink: 0;">
                        <span style="display: inline-flex; align-items: center; gap: 6px;">
                          <sc-if value="{{ t.hasPj }}" hint-placeholder-val="{{ true }}">
                            <span title="{{ t.pjTitle }}" class="ic" style="width: 12px; height: 12px; color: {{ t.pjColor }}; -webkit-mask-image: url('{{ t.pjIcon }}'); mask-image: url('{{ t.pjIcon }}');"></span>
                          </sc-if>
                          <span title="Messages dans ce fil" style="display: inline-flex; align-items: center; gap: 5px; height: 18px; padding: 0 7px; border-radius: 5px; border: 1px solid rgba(var(--w), 0.12);">
                            <span class="ic" style="width: 10px; height: 10px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/messages-square.svg'); mask-image: url('./assets/icons/messages-square.svg');"></span>
                            <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx3);">{{ t.count }}</span>
                          </span>
                        </span>
                        <span style="display: inline-flex; align-items: center; gap: 5px;">
                          <span class="ic" style="width: 11px; height: 11px; color: {{ t.statusColor }}; -webkit-mask-image: url('{{ t.statusIcon }}'); mask-image: url('{{ t.statusIcon }}');"></span>
                          <span style="font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.05em; text-transform: uppercase; color: {{ t.statusColor }};">{{ t.status }}</span>
                        </span>
                        <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5);">{{ t.last }}</span>
                      </span>
                    </div>
                    <sc-if value="{{ t.open }}" hint-placeholder-val="{{ true }}">
                      <div class="unfold" style="display: flex; flex-direction: column; padding: 0 0 8px 28px;">
                        <sc-for list="{{ t.items }}" as="m" hint-placeholder-count="3">
                          <div onClick="{{ m.pick }}" class="row-in" style="animation-delay: {{ m.rowDelay }}; display: flex; align-items: stretch; gap: 0; padding: 0 14px 0 10px; border-left: 2px solid {{ m.mark }}; background: {{ m.bg }}; cursor: pointer; transition: background 130ms ease;" style-hover="background: rgba(var(--w), 0.045);">
                            <sc-for list="{{ m.rails }}" as="r" hint-placeholder-count="1">
                              <span style="width: 15px; flex-shrink: 0; margin-left: {{ r.ml }}; height: {{ r.h }}; border-left: 1px solid {{ r.line }}; border-bottom: 1px solid {{ r.bottom }}; border-bottom-left-radius: {{ r.radius }};"></span>
                            </sc-for>
                            <span style="width: 6px; height: 6px; margin: 10px 9px 0 {{ m.dotGap }}; border-radius: 9999px; background: {{ m.statusColor }}; flex-shrink: 0;"></span>
                            <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; padding: 8px 0 9px;">
                              <span style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5); white-space: nowrap;">{{ m.when }}</span>
                                <span style="font-family: var(--font-mono); font-size: 10.5px; color: var(--tx3); white-space: nowrap;">{{ m.from }}</span>
                                <span class="ic" style="width: 10px; height: 10px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/arrow-right.svg'); mask-image: url('./assets/icons/arrow-right.svg');"></span>
                                <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 10.5px; color: var(--tx4); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ m.to }}</span>
                                <sc-if value="{{ m.hasPj }}" hint-placeholder-val="{{ true }}">
                                  <span title="{{ m.pjTitle }}" class="ic" style="width: 11px; height: 11px; color: {{ m.pjColor }}; -webkit-mask-image: url('{{ m.pjIcon }}'); mask-image: url('{{ m.pjIcon }}');"></span>
                                </sc-if>
                                <span style="font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.05em; text-transform: uppercase; color: {{ m.statusColor }}; white-space: nowrap;">{{ m.status }}</span>
                              </span>
                              <span style="font-size: 12px; color: {{ m.objetColor }}; font-weight: {{ m.weight }}; line-height: 1.4; text-wrap: pretty;">{{ m.short }}</span>
                            </span>
                          </div>
                        </sc-for>
                      </div>
                    </sc-if>
                  </div>
                </sc-for>
                <sc-if value="{{ emptyList }}" hint-placeholder-val="{{ false }}">
                  <span style="font-size: 12.5px; color: var(--tx4); padding: 16px;">{{ emptyLabel }}</span>
                </sc-if>
              </div>
            </sc-if>
            <sc-if value="{{ flatView }}" hint-placeholder-val="{{ false }}">
              <div style="display: flex; flex-direction: column;">
                <sc-for list="{{ messages }}" as="m" hint-placeholder-count="10">
                  <div onClick="{{ m.pick }}" class="{{ m.anim }}" style="display: flex; flex-direction: column; gap: 6px; padding: 10px 16px 11px; border-bottom: 1px solid rgba(var(--w), 0.05); border-left: 2px solid {{ m.mark }}; cursor: pointer; background: {{ m.bg }}; transition: background 130ms ease; animation-delay: {{ m.delay }};" style-hover="background: rgba(var(--w), 0.045);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5); width: 44px; flex-shrink: 0;">{{ m.hhmm }}</span>
                      <span style="font-family: var(--font-mono); font-size: 10.5px; color: var(--tx3); white-space: nowrap;">{{ m.from }}</span>
                      <span class="ic" style="width: 11px; height: 11px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/arrow-right.svg'); mask-image: url('./assets/icons/arrow-right.svg');"></span>
                      <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 10.5px; color: var(--tx4); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ m.to }}</span>
                      <sc-for list="{{ m.tags }}" as="p" hint-placeholder-count="1">
                        <span title="{{ p.title }}" style="display: inline-flex; align-items: center; height: 16px; padding: 0 6px; border-radius: 4px; border: 1px solid {{ p.tint }}; font-family: var(--font-mono); font-size: 9px; color: {{ p.tint }}; white-space: nowrap;">{{ p.name }}</span>
                      </sc-for>
                      <sc-if value="{{ m.hasPj }}" hint-placeholder-val="{{ true }}">
                        <span title="{{ m.pjTitle }}" class="ic" style="width: 12px; height: 12px; color: {{ m.pjColor }}; -webkit-mask-image: url('{{ m.pjIcon }}'); mask-image: url('{{ m.pjIcon }}');"></span>
                      </sc-if>
                      <span style="display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; width: 76px; justify-content: flex-end;">
                        <span class="ic" style="width: 11px; height: 11px; color: {{ m.statusColor }}; -webkit-mask-image: url('{{ m.statusIcon }}'); mask-image: url('{{ m.statusIcon }}');"></span>
                        <span style="font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.05em; text-transform: uppercase; color: {{ m.statusColor }};">{{ m.status }}</span>
                      </span>
                    </div>
                    <span style="font-size: 12.5px; color: {{ m.objetColor }}; font-weight: {{ m.weight }}; line-height: 1.4; padding-left: 52px; text-wrap: pretty;">{{ m.objet }}</span>
                    <sc-if value="{{ m.forMe }}" hint-placeholder-val="{{ true }}">
                      <span style="display: inline-flex; align-self: flex-start; align-items: center; gap: 6px; margin-left: 52px; height: 18px; padding: 0 7px; border-radius: 5px; border: 1px solid {{ m.roleBorder }}; background: {{ m.roleBg }};">
                        <span class="ic" style="width: 11px; height: 11px; color: {{ m.roleColor }}; -webkit-mask-image: url('{{ m.roleIcon }}'); mask-image: url('{{ m.roleIcon }}');"></span>
                        <span style="font-size: 10.5px; color: {{ m.roleColor }}; white-space: nowrap;">{{ m.roleLabel }}</span>
                      </span>
                    </sc-if>
                  </div>
                </sc-for>
                <sc-if value="{{ emptyList }}" hint-placeholder-val="{{ false }}">
                  <span style="font-size: 12.5px; color: var(--tx4); padding: 16px;">{{ emptyLabel }}</span>
                </sc-if>
              </div>
            </sc-if>
          </div>
        </div>

        <div style="width: 404px; flex-shrink: 0; display: flex; flex-direction: column; min-height: 0; background: var(--zone);">
          <div style="display: flex; align-items: center; gap: 10px; height: 30px; padding: 0 16px; background: var(--head); border-bottom: 1px solid rgba(var(--w), 0.07); flex-shrink: 0;">
            <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--tx5);">Message</span>
            <span style="flex: 1;"></span>
            <span title="{{ sel.id }}" style="max-width: 250px; font-family: var(--font-mono); font-size: 9.5px; color: var(--tx5); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ sel.id }}</span>
          </div>
          <div key="{{ sel.id }}" class="rise" style="flex: 1; overflow-y: auto; min-height: 0; padding: 16px 18px 22px; display: flex; flex-direction: column; gap: 17px;">
            <div style="display: flex; flex-direction: column; gap: 10px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <sc-for list="{{ sel.tags }}" as="p" hint-placeholder-count="1">
                  <span title="{{ p.title }}" style="display: inline-flex; align-items: center; height: 17px; padding: 0 6px; border-radius: 4px; border: 1px solid {{ p.tint }}; font-family: var(--font-mono); font-size: 9.5px; color: {{ p.tint }};">{{ p.name }}</span>
                </sc-for>
                <span style="flex: 1;"></span>
                <span style="font-family: var(--font-mono); font-size: 10.5px; color: var(--tx5);">{{ sel.stamp }}</span>
              </div>
              <span style="font-size: 14px; font-weight: 600; color: var(--tx1); line-height: 1.4; text-wrap: pretty;">{{ sel.objet }}</span>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; align-items: baseline; gap: 9px;">
                  <span style="width: 22px; font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.08em; color: var(--tx5); flex-shrink: 0;">DE</span>
                  <span style="font-family: var(--font-mono); font-size: 11px; color: var(--tx2);">{{ sel.from }}</span>
                </div>
                <div style="display: flex; align-items: baseline; gap: 9px;">
                  <span style="width: 22px; font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.08em; color: var(--tx5); flex-shrink: 0;">À</span>
                  <span style="display: flex; flex-direction: column; gap: 4px; min-width: 0;">
                    <sc-for list="{{ sel.recips }}" as="r" hint-placeholder-count="2">
                      <span title="{{ r.title }}" style="display: flex; align-items: center; gap: 7px;">
                        <span style="width: 5px; height: 5px; border-radius: 9999px; background: {{ r.dot }}; flex-shrink: 0;"></span>
                        <span style="font-family: var(--font-mono); font-size: 11px; color: {{ r.color }};">{{ r.name }}</span>
                        <span style="font-family: var(--font-mono); font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase; color: var(--tx5);">{{ r.status }}</span>
