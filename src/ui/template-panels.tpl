                      </span>
                    </sc-for>
                  </span>
                </div>
              </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 10px; padding: 12px 13px 13px; border: 1px solid {{ sel.askBorder }}; border-radius: 9px; background: {{ sel.askBg }};">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="ic" style="width: 13px; height: 13px; color: {{ sel.askColor }}; -webkit-mask-image: url('{{ sel.askIcon }}'); mask-image: url('{{ sel.askIcon }}');"></span>
                <span style="font-size: 12px; font-weight: 600; color: {{ sel.askColor }};">{{ sel.askTitle }}</span>
              </div>
              <span style="font-size: 12px; color: var(--tx3); line-height: 1.55; text-wrap: pretty;">{{ sel.askText }}</span>
              <div style="display: flex; align-items: center; gap: 0;">
                <sc-for list="{{ sel.steps }}" as="s" hint-placeholder-count="3">
                  <span title="{{ s.title }}" style="display: flex; align-items: center; gap: 7px; padding-right: 10px;">
                    <span class="{{ s.pulse }}" style="width: 7px; height: 7px; border-radius: 9999px; background: {{ s.dot }}; transition: background 300ms ease;"></span>
                    <span style="font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: {{ s.color }}; transition: color 300ms ease;">{{ s.label }}</span>
                    <span style="width: 16px; height: 1px; background: {{ s.line }};"></span>
                  </span>
                </sc-for>
              </div>
              <span style="font-size: 11.5px; color: var(--tx3);">{{ sel.journey }}</span>
              <span style="font-size: 11.5px; color: var(--tx4); line-height: 1.5;">{{ sel.reach }}</span>
              <sc-for list="{{ sel.history }}" as="h"><span style="font-size: 11px; color: var(--tx4);">{{ h.line }}</span></sc-for>
            </div>

            <div style="display: flex; flex-direction: column; gap: 8px;">
              <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Corps</span>
              <sc-for list="{{ sel.body }}" as="b" hint-placeholder-count="2">
                <span style="font-size: 12.5px; color: var(--tx3); line-height: 1.6; text-wrap: pretty;">{{ b.line }}</span>
              </sc-for>
              <sc-if value="{{ sel.noBody }}" hint-placeholder-val="{{ false }}">
                <span style="font-size: 12px; color: var(--tx4);">Aucun — l'objet suffit.</span>
              </sc-if>
            </div>

            <div style="display: flex; flex-direction: column; gap: 8px;">
              <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Pièce jointe</span>
              <sc-if value="{{ sel.hasPj }}" hint-placeholder-val="{{ true }}">
                <div onClick="{{ sel.openPj }}" title="{{ sel.pjTitle }}" style="display: flex; align-items: center; gap: 10px; padding: 10px 11px; border: 1px solid {{ sel.pjBorder }}; border-radius: 8px; cursor: pointer;" style-hover="background: rgba(var(--w), 0.04);">
                  <span class="ic" style="width: 15px; height: 15px; color: {{ sel.pjColor }}; -webkit-mask-image: url('{{ sel.pjIcon }}'); mask-image: url('{{ sel.pjIcon }}');"></span>
                  <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 11px; color: var(--tx2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ sel.pj }}</span>
                  <span style="font-size: 10.5px; color: {{ sel.pjColor }}; white-space: nowrap;">{{ sel.pjState }}</span>
                </div>
                <sc-if value="{{ sel.canSavePj }}"><button onClick="{{ sel.savePj }}" style="align-self: flex-start; border: 0; background: transparent; color: var(--tx3); cursor: pointer;">Enregistrer une copie</button></sc-if>
              </sc-if>
              <sc-if value="{{ sel.noPj }}" hint-placeholder-val="{{ false }}">
                <span style="font-size: 12px; color: var(--tx4);">Aucune — le corps suffit.</span>
              </sc-if>
            </div>

            <div style="display: flex; flex-direction: column; gap: 8px;">
              <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Fil</span>
              <sc-for list="{{ sel.thread }}" as="t" hint-placeholder-count="2">
                <div onClick="{{ t.pick }}" style="display: flex; align-items: flex-start; gap: 9px; padding: 8px 9px; border-radius: 7px; cursor: pointer; background: {{ t.bg }};" style-hover="background: rgba(var(--w), 0.05);">
                  <span style="width: 5px; height: 5px; margin-top: 6px; border-radius: 9999px; background: {{ t.dot }}; flex-shrink: 0;"></span>
                  <span style="display: flex; flex-direction: column; gap: 3px; min-width: 0;">
                    <span style="font-family: var(--font-mono); font-size: 9.5px; color: var(--tx5); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ t.id }}</span>
                    <span style="font-size: 12px; color: var(--tx2); line-height: 1.4; text-wrap: pretty;">{{ t.objet }}</span>
                  </span>
                </div>
              </sc-for>
              <sc-if value="{{ sel.noThread }}" hint-placeholder-val="{{ false }}">
                <span style="font-size: 12px; color: var(--tx4);">Pas de réponse à ce jour.</span>
              </sc-if>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>

  <footer style="display: flex; align-items: center; gap: 14px; height: 28px; padding: 0 14px; background: var(--bar); border-top: 1px solid rgba(var(--w), 0.07); flex-shrink: 0;">
    <span style="font-family: var(--font-mono); font-size: 9.5px; color: var(--tx5);">{{ footStat }}</span>
    <span style="flex: 1;"></span>
    <span style="font-family: var(--font-mono); font-size: 9.5px; color: var(--tx5);">{{ footSource }}</span>
  </footer>

  <sc-if value="{{ agentOpen }}" hint-placeholder-val="{{ false }}">
    <div class="{{ panelAnim }}" style="position: absolute; top: 46px; right: 0; bottom: 28px; width: 436px; box-sizing: border-box; background: var(--zone); border-left: 1px solid rgba(var(--w), 0.12); box-shadow: -10px 0 26px -16px rgba(0, 0, 0, 0.55); display: flex; flex-direction: column; z-index: 40;">
      <div style="display: flex; align-items: flex-start; gap: 10px; padding: 15px 16px 14px; border-bottom: 1px solid rgba(var(--w), 0.07);">
        <span class="{{ ag.pulse }}" style="width: 7px; height: 7px; margin-top: 6px; border-radius: 9999px; background: {{ ag.dot }}; flex-shrink: 0;"></span>
        <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px;">
          <span style="font-size: 14px; font-weight: 600; color: var(--tx1); line-height: 1.3;">{{ ag.name }}</span>
          <span title="Son adresse dans la boîte" style="font-family: var(--font-mono); font-size: 10.5px; color: var(--tx5); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ ag.address }}</span>
        </span>
        <span onClick="{{ closeAgent }}" title="Fermer la fiche" class="ic" style="width: 15px; height: 15px; margin-top: 3px; color: var(--tx4); cursor: pointer; -webkit-mask-image: url('./assets/icons/x.svg'); mask-image: url('./assets/icons/x.svg');"></span>
      </div>
      <div style="flex: 1; overflow-y: auto; min-height: 0; padding: 15px 16px 20px; display: flex; flex-direction: column; gap: 16px;">
        <div style="display: flex; flex-direction: column; gap: 7px;">
          <sc-if value="{{ ag.acct.viewing }}" hint-placeholder-val="{{ true }}">
            <span style="font-size: 12.5px; color: var(--tx2); line-height: 1.55; text-wrap: pretty;">{{ ag.role }}</span>
          </sc-if>
          <sc-if value="{{ ag.acct.editing }}" hint-placeholder-val="{{ false }}">
            <div class="fade-in" style="display: flex; align-items: center; gap: 7px;">
              <input ref="{{ ag.acct.focus }}" value="{{ ag.acct.roleDraft }}" onChange="{{ ag.acct.onRoleDraft }}" onKeyDown="{{ ag.acct.roleKey }}" placeholder="Son rôle, sur une ligne (ex. relecture du code)" aria-label="Le rôle de cet agent" autocomplete="off" style="flex: 1; min-width: 0; height: 30px; box-sizing: border-box; padding: 0 10px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.16); background: transparent; outline: none; font-family: var(--font-ui); font-size: 12.5px; color: var(--tx1);" />
              <button type="button" onClick="{{ ag.acct.saveRole }}" style="height: 30px; padding: 0 10px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.2); background: rgba(var(--w), 0.08); font-family: var(--font-ui); font-size: 12px; color: var(--tx1); cursor: pointer;">Enregistrer</button>
              <button type="button" onClick="{{ ag.acct.cancelRole }}" style="height: 30px; padding: 0 10px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.12); background: transparent; font-family: var(--font-ui); font-size: 12px; color: var(--tx3); cursor: pointer;">Annuler</button>
            </div>
          </sc-if>
          <div style="display: flex; align-items: center; gap: 10px;">
            <span title="Outil d’IA et ordinateur de cet agent" style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 10.5px; color: var(--tx5); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ ag.post }}</span>
            <sc-if value="{{ ag.acct.viewing }}" hint-placeholder-val="{{ true }}">
              <span onClick="{{ ag.acct.editRole }}" style="font-size: 11.5px; color: var(--tx3); cursor: pointer; white-space: nowrap; text-decoration: underline; text-underline-offset: 3px; text-decoration-color: rgba(var(--w), 0.2);">Modifier le rôle</span>
            </sc-if>
          </div>
          <sc-if value="{{ ag.acct.noticeAtRole }}" hint-placeholder-val="{{ false }}">
            <span ref="{{ ag.acct.reveal }}" role="alert" style="font-size: 11.5px; color: var(--fail-tx); line-height: 1.5;">{{ ag.acct.notice }}</span>
          </sc-if>
        </div>

        <sc-if value="{{ ag.alert }}" hint-placeholder-val="{{ true }}">
          <div style="display: flex; flex-direction: column; gap: 8px; padding: 12px 13px; border: 1px solid rgba(217, 119, 6, 0.32); border-radius: 9px; background: rgba(217, 119, 6, 0.10);">
            <span style="font-size: 12px; font-weight: 600; color: var(--warn-tx);">{{ ag.alertTitle }}</span>
            <span style="font-size: 12px; color: var(--tx3); line-height: 1.55; text-wrap: pretty;">{{ ag.alertText }}</span>
          </div>
        </sc-if>

        <div style="display: flex; flex-direction: column; gap: 9px; padding: 13px 14px 14px; border: 1px solid rgba(var(--w), 0.1); border-radius: 10px;">
          <div style="display: flex; align-items: center; gap: 9px;">
            <span class="ic" style="width: 14px; height: 14px; color: var(--tx3); -webkit-mask-image: url('./assets/icons/contact-round.svg'); mask-image: url('./assets/icons/contact-round.svg');"></span>
            <span style="font-size: 12.5px; font-weight: 600; color: var(--tx1);">Carnet d'adresses</span>
            <span key="{{ ag.contactCount }}" class="pop" style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5);">{{ ag.contactCount }}</span>
            <span style="flex: 1;"></span>
            <span onClick="{{ ag.openAdv }}" style="display: inline-flex; align-items: center; gap: 6px; height: 25px; padding: 0 9px; border-radius: 6px; border: 1px solid rgba(var(--w), 0.14); font-size: 11.5px; color: var(--tx2); cursor: pointer; white-space: nowrap;" style-hover="background: rgba(var(--w), 0.06);">
              <span class="ic" style="width: 11px; height: 11px; color: var(--tx3); -webkit-mask-image: url('./assets/icons/plus.svg'); mask-image: url('./assets/icons/plus.svg');"></span>
              Ajouter
            </span>
          </div>
          <span style="font-size: 11.5px; color: var(--tx5); line-height: 1.5;">Les noms courts que cet agent utilise pour écrire aux autres.</span>
          <sc-for list="{{ ag.contacts }}" as="c" hint-placeholder-count="1">
            <div class="rise" style="display: flex; align-items: flex-start; gap: 10px; padding: 10px 11px; border: 1px solid rgba(var(--w), 0.08); border-radius: 8px; background: rgba(var(--w), 0.025);">
              <span style="display: flex; flex-direction: column; gap: 5px; flex: 1; min-width: 0;">
                <span style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span style="font-family: var(--font-mono); font-size: 11.5px; font-weight: 700; color: var(--tx1);">{{ c.alias }}</span>
                  <span class="ic" style="width: 11px; height: 11px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/arrow-right.svg'); mask-image: url('./assets/icons/arrow-right.svg');"></span>
                  <span style="font-family: var(--font-mono); font-size: 11px; color: var(--tx3);">{{ c.targets }}</span>
                </span>
                <span style="font-size: 11.5px; color: var(--tx4); line-height: 1.45; text-wrap: pretty;">{{ c.note }}</span>
              </span>
              <span onClick="{{ c.remove }}" title="Retirer ce contact" class="ic" style="width: 13px; height: 13px; margin-top: 2px; color: var(--tx5); cursor: pointer; -webkit-mask-image: url('./assets/icons/trash.svg'); mask-image: url('./assets/icons/trash.svg');"></span>
            </div>
          </sc-for>
          <sc-if value="{{ ag.noContacts }}" hint-placeholder-val="{{ false }}">
            <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">Aucun contact. Un contact donne un nom court à un agent, ou à un groupe, à qui il écrit souvent.</span>
          </sc-if>
        </div>

        <div style="display: flex; flex-direction: column; gap: 10px;">
          <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Son courrier</span>
          <div style="display: flex; gap: 9px;">
            <sc-for list="{{ ag.stats }}" as="s" hint-placeholder-count="3">
              <div style="flex: 1; display: flex; flex-direction: column; gap: 5px; padding: 10px 11px; border: 1px solid rgba(var(--w), 0.09); border-radius: 8px;">
                <span key="{{ s.value }}" class="pop" style="font-family: var(--font-sans); font-size: 19px; font-weight: 900; letter-spacing: -0.02em; color: {{ s.color }};">{{ s.value }}</span>
                <span style="font-size: 10.5px; color: var(--tx4); line-height: 1.35;">{{ s.label }}</span>
              </div>
            </sc-for>
          </div>
          <div onClick="{{ ag.filter }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.12); cursor: pointer;" style-hover="background: rgba(var(--w), 0.05);">
            <span class="ic" style="width: 13px; height: 13px; color: var(--tx4); -webkit-mask-image: url('./assets/icons/list-filter.svg'); mask-image: url('./assets/icons/list-filter.svg');"></span>
            <span style="font-size: 12px; color: var(--tx2);">{{ ag.filterLabel }}</span>
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 9px;">
          <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Le remettre au travail</span>
          <span style="font-size: 12px; color: var(--tx4); line-height: 1.55;">À coller dans le chat de cet agent : il reprend ce compte et relève son courrier.</span>
          <div onClick="{{ ag.copy }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 30px; padding: 0 12px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.14); cursor: pointer;" style-hover="background: rgba(var(--w), 0.06);">
            <span class="ic" style="width: 13px; height: 13px; color: var(--tx2); -webkit-mask-image: url('{{ ag.copyIcon }}'); mask-image: url('{{ ag.copyIcon }}');"></span>
            <span style="font-size: 12.5px; font-weight: 500; color: var(--tx1);">{{ ag.copyLabel }}</span>
          </div>
        </div>

        <div onClick="{{ ag.openAdv }}" style="display: flex; align-items: center; gap: 9px; padding: 11px 12px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.09); cursor: pointer;" style-hover="background: rgba(var(--w), 0.05);">
          <span class="ic" style="width: 14px; height: 14px; color: var(--tx4); -webkit-mask-image: url('./assets/icons/sliders-horizontal.svg'); mask-image: url('./assets/icons/sliders-horizontal.svg');"></span>
          <span style="flex: 1; display: flex; flex-direction: column; gap: 3px;">
            <span style="font-size: 12.5px; color: var(--tx1);">Options avancées</span>
            <span style="font-size: 11px; color: var(--tx5);">Ranger dans un projet, fusionner deux comptes, ajouter un contact</span>
          </span>
          <span class="ic" style="width: 13px; height: 13px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/chevron-right.svg'); mask-image: url('./assets/icons/chevron-right.svg');"></span>
        </div>

        <sc-if value="{{ ag.acct.idle }}" hint-placeholder-val="{{ true }}">
          <span onClick="{{ ag.acct.askDeactivate }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(190, 18, 60, 0.3); cursor: pointer;" style-hover="background: rgba(190, 18, 60, 0.08);">
            <span class="ic" style="width: 13px; height: 13px; color: var(--fail-tx); -webkit-mask-image: url('./assets/icons/user-round-x.svg'); mask-image: url('./assets/icons/user-round-x.svg');"></span>
            <span style="font-size: 12px; color: var(--fail-tx);">Désactiver le compte</span>
          </span>
        </sc-if>
        <sc-if value="{{ ag.acct.confirming }}" hint-placeholder-val="{{ false }}">
          <div ref="{{ ag.acct.reveal }}" class="fade-in" style="display: flex; flex-direction: column; gap: 8px; padding: 12px 13px; border: 1px solid rgba(190, 18, 60, 0.32); border-radius: 9px; background: rgba(190, 18, 60, 0.06);">
            <span style="font-size: 12px; font-weight: 600; color: var(--fail-tx);">Désactiver ce compte ?</span>
            <span style="font-size: 12px; color: var(--tx3); line-height: 1.55; text-wrap: pretty;">{{ ag.acct.consequence }}</span>
            <sc-if value="{{ ag.acct.hasWaiting }}" hint-placeholder-val="{{ false }}">
              <span style="font-size: 12px; color: var(--warn-tx); line-height: 1.55; text-wrap: pretty;">{{ ag.acct.waitingText }}</span>
            </sc-if>
            <div style="display: flex; gap: 8px;">
              <sc-if value="{{ ag.acct.hasWaiting }}" hint-placeholder-val="{{ false }}">
                <button type="button" onClick="{{ ag.acct.mergeInstead }}" style="height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.2); background: rgba(var(--w), 0.08); font-family: var(--font-ui); font-size: 12px; color: var(--tx1); cursor: pointer;">Fusionner plutôt</button>
              </sc-if>
              <button type="button" onClick="{{ ag.acct.deactivate }}" style="height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(190, 18, 60, 0.4); background: transparent; font-family: var(--font-ui); font-size: 12px; color: var(--fail-tx); cursor: pointer;">Désactiver</button>
              <button type="button" onClick="{{ ag.acct.cancelDeactivate }}" style="height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.12); background: transparent; font-family: var(--font-ui); font-size: 12px; color: var(--tx3); cursor: pointer;">Annuler</button>
            </div>
            <sc-if value="{{ ag.acct.noticeAtDeactivate }}" hint-placeholder-val="{{ false }}">
              <span role="alert" style="font-size: 11.5px; color: var(--fail-tx); line-height: 1.5;">{{ ag.acct.notice }}</span>
            </sc-if>
          </div>
        </sc-if>
      </div>
    </div>
  </sc-if>

  <sc-if value="{{ modalOpen }}" hint-placeholder-val="{{ false }}">
    <div role="presentation" onClick="{{ closeModal }}" class="fade-in" style="position: absolute; inset: 0; background: rgba(0, 0, 0, 0.5); display: flex; align-items: center; justify-content: center; padding: 40px; z-index: 60;">
      <div role="dialog" aria-modal="true" aria-label="{{ modal.title }}" tabindex="-1" onClick="{{ stop }}" class="modal-in" style="width: {{ modal.width }}; max-height: 100%; box-sizing: border-box; display: flex; flex-direction: column; background: var(--elevated); border: 1px solid rgba(var(--w), 0.1); border-radius: 14px; box-shadow: 0 30px 80px rgba(0, 0, 0, 0.45); overflow: hidden;">
        <div style="display: flex; align-items: flex-start; gap: 12px; padding: 18px 20px 16px; border-bottom: 1px solid rgba(var(--w), 0.07);">
          <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px;">
            <span style="font-size: 16px; font-weight: 600; color: var(--tx1); line-height: 1.3;">{{ modal.title }}</span>
            <span style="font-size: 12.5px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">{{ modal.intro }}</span>
          </span>
          <span data-modal-close="" onClick="{{ closeModal }}" title="Fermer" class="ic" style="width: 16px; height: 16px; margin-top: 3px; color: var(--tx4); cursor: pointer; -webkit-mask-image: url('./assets/icons/x.svg'); mask-image: url('./assets/icons/x.svg');"></span>
        </div>

        <div style="flex: 1; overflow-y: auto; min-height: 0; padding: 18px 20px 20px; display: flex; flex-direction: column; gap: 18px;">

          <span role="alert" style="font-size: 12px; color: var(--fail-tx);">{{ modal.providerNotice }}</span>
          <sc-if value="{{ modal.isSetup }}" hint-placeholder-val="{{ false }}">
            <div style="display: flex; flex-direction: column; gap: 10px;">
              <sc-for list="{{ modal.steps }}" as="s" hint-placeholder-count="3">
                <div style="display: flex; align-items: flex-start; gap: 13px; padding: 14px 15px; border: 1px solid {{ s.border }}; border-radius: 10px; background: {{ s.bg }};">
                  <span style="width: 25px; height: 25px; border-radius: 9999px; border: 1px solid {{ s.numBorder }}; background: {{ s.numBg }}; color: {{ s.numColor }}; font-family: var(--font-mono); font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">{{ s.n }}</span>
                  <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px;">
                    <span style="display: flex; align-items: center; gap: 9px;">
                      <span style="font-size: 13px; font-weight: 600; color: var(--tx1);">{{ s.title }}</span>
                      <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.06em; color: {{ s.stateColor }};">{{ s.state }}</span>
                    </span>
                    <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">{{ s.text }}</span>
                    <sc-if value="{{ s.hasCta }}" hint-placeholder-val="{{ true }}">
                      <span onClick="{{ s.act }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 30px; padding: 0 12px; margin-top: 2px; border-radius: 7px; border: 1px solid {{ s.ctaBorder }}; background: {{ s.ctaBg }}; cursor: pointer;" style-hover="background: rgba(var(--w), 0.07);">
                        <span class="ic" style="width: 13px; height: 13px; color: {{ s.ctaColor }}; -webkit-mask-image: url('{{ s.ctaIcon }}'); mask-image: url('{{ s.ctaIcon }}');"></span>
                        <span style="font-size: 12.5px; font-weight: 500; color: {{ s.ctaColor }};">{{ s.cta }}</span>
                      </span>
                    </sc-if>
                  </span>
                </div>
              </sc-for>
            </div>
          </sc-if>

          <sc-if value="{{ modal.isProject }}" hint-placeholder-val="{{ false }}">
            <div style="display: flex; flex-direction: column; gap: 7px;">
              <span style="font-size: 12px; font-weight: 600; color: var(--tx2);">Le nom du projet</span>
              <input value="{{ modal.projName }}" onChange="{{ modal.onProjName }}" placeholder="{{ modal.projectPlaceholder }}" aria-label="Le nom du projet" autocomplete="off" style="height: 36px; box-sizing: border-box; padding: 0 12px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.12); background: transparent; outline: none; font-family: var(--font-mono); font-size: 12.5px; color: var(--tx1);" />
              <sc-if value="{{ modal.normalized }}" hint-placeholder-val="{{ false }}">
                <span class="fade-in" style="font-size: 11.5px; color: var(--tx4);">{{ modal.normalizedText }}</span>
              </sc-if>
            </div>
          </sc-if>

          <sc-if value="{{ modal.isInvite }}" hint-placeholder-val="{{ false }}">
            <div style="display: flex; flex-direction: column; gap: 13px;">
              <span style="font-size: 12px; font-weight: 600; color: var(--tx2);">Dans quel projet ?</span>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                <sc-for list="{{ modal.choices }}" as="c" hint-placeholder-count="3">
                  <div onClick="{{ c.pick }}" style="display: flex; align-items: center; gap: 11px; padding: 11px 12px; border-radius: 8px; border: 1px solid {{ c.border }}; background: {{ c.bg }}; cursor: pointer; transition: background 140ms ease, border-color 140ms ease;" style-hover="background: rgba(var(--w), 0.05);">
                    <span style="width: 15px; height: 15px; border-radius: 9999px; border: 1px solid {{ c.ring }}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                      <span style="width: 7px; height: 7px; border-radius: 9999px; background: {{ c.inner }}; transition: background 160ms ease;"></span>
                    </span>
                    <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px;">
                      <span style="font-family: var(--font-mono); font-size: 12px; color: {{ c.color }};">{{ c.name }}{{ c.label }}</span>
                      <span style="font-size: 11px; color: var(--tx5); line-height: 1.4;">{{ c.hint }}</span>
                    </span>
                  </div>
                </sc-for>
              </div>
              <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">Tu obtiens un texte à coller dans le chat de ton agent. Il y lit son projet et crée son compte tout seul.</span>
              <sc-if value="{{ modal.copied }}" hint-placeholder-val="{{ false }}">
                <span class="fade-in" style="font-size: 12px; color: var(--pass-tx); line-height: 1.5;">Invite copiée. Tu peux la coller à plusieurs agents : la même invite sert à tous ceux du projet.</span>
              </sc-if>
            </div>
          </sc-if>

          <sc-if value="{{ modal.isAdv }}" hint-placeholder-val="{{ false }}">
            <div style="display: flex; flex-direction: column; gap: 18px;">
              <div style="display: flex; flex-direction: column; gap: 8px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Rôle</span>
                <sc-if value="{{ modal.acct.viewing }}" hint-placeholder-val="{{ true }}">
                  <div style="display: flex; align-items: baseline; gap: 10px;">
                    <span style="flex: 1; min-width: 0; font-size: 12.5px; color: var(--tx3); line-height: 1.55; text-wrap: pretty;">{{ modal.role }}</span>
                    <span onClick="{{ modal.acct.editRole }}" style="font-size: 11.5px; color: var(--tx3); cursor: pointer; white-space: nowrap; text-decoration: underline; text-underline-offset: 3px; text-decoration-color: rgba(var(--w), 0.2);">Modifier le rôle</span>
                  </div>
                </sc-if>
                <sc-if value="{{ modal.acct.editing }}" hint-placeholder-val="{{ false }}">
                  <div class="fade-in" style="display: flex; align-items: center; gap: 7px;">
                    <input ref="{{ modal.acct.focus }}" value="{{ modal.acct.roleDraft }}" onChange="{{ modal.acct.onRoleDraft }}" onKeyDown="{{ modal.acct.roleKey }}" placeholder="Son rôle, sur une ligne (ex. relecture du code)" aria-label="Le rôle de cet agent" autocomplete="off" style="flex: 1; min-width: 0; height: 34px; box-sizing: border-box; padding: 0 11px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.16); background: transparent; outline: none; font-family: var(--font-ui); font-size: 12.5px; color: var(--tx1);" />
                    <button type="button" onClick="{{ modal.acct.saveRole }}" style="height: 34px; padding: 0 11px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.2); background: rgba(var(--w), 0.08); font-family: var(--font-ui); font-size: 12px; color: var(--tx1); cursor: pointer;">Enregistrer</button>
                    <button type="button" onClick="{{ modal.acct.cancelRole }}" style="height: 34px; padding: 0 11px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.12); background: transparent; font-family: var(--font-ui); font-size: 12px; color: var(--tx3); cursor: pointer;">Annuler</button>
                  </div>
                </sc-if>
                <span title="Outil d’IA et ordinateur de cet agent" style="font-family: var(--font-mono); font-size: 10.5px; color: var(--tx5);">{{ modal.post }}</span>
                <sc-if value="{{ modal.acct.noticeAtRole }}" hint-placeholder-val="{{ false }}">
                  <span ref="{{ modal.acct.reveal }}" role="alert" style="font-size: 11.5px; color: var(--fail-tx); line-height: 1.5;">{{ modal.acct.notice }}</span>
                </sc-if>
              </div>

              <div style="display: flex; flex-direction: column; gap: 8px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Projet</span>
                <span style="font-size: 12.5px; color: var(--tx3); line-height: 1.55; text-wrap: pretty;">{{ modal.projectText }}</span>
                <sc-if value="{{ modal.canFile }}" hint-placeholder-val="{{ true }}">
                  <div style="display: flex; flex-wrap: wrap; gap: 7px;">
                    <sc-for list="{{ modal.fileChoices }}" as="f" hint-placeholder-count="3">
                      <span onClick="{{ f.pick }}" style="display: inline-flex; align-items: center; height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid {{ f.border }}; background: {{ f.bg }}; font-family: var(--font-mono); font-size: 11.5px; color: {{ f.color }}; cursor: pointer; transition: background 140ms ease;" style-hover="background: rgba(var(--w), 0.06);">{{ f.name }}{{ f.label }}</span>
                    </sc-for>
                  </div>
                  <span style="font-size: 11.5px; color: var(--tx5); line-height: 1.5;">Son adresse ne change pas : son courrier et son carnet restent valables.</span>
                </sc-if>
              </div>

              <div style="display: flex; flex-direction: column; gap: 8px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Deux comptes, un agent ?</span>
                <div style="display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 11px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.12);">
                  <span class="ic" style="width: 13px; height: 13px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/search.svg'); mask-image: url('./assets/icons/search.svg');"></span>
                  <input value="{{ modal.mergeQuery }}" onChange="{{ modal.onMergeQuery }}" placeholder="Chercher un compte" style="flex: 1; min-width: 0; border: none; outline: none; background: transparent; font-family: var(--font-mono); font-size: 12px; color: var(--tx1);" />
                  <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5); white-space: nowrap;">{{ modal.mergeCount }}</span>
                </div>
                <div style="max-height: 176px; overflow-y: auto; border: 1px solid rgba(var(--w), 0.08); border-radius: 8px;">
                  <sc-for list="{{ modal.mergeGroups }}" as="g" hint-placeholder-count="2">
                    <div style="display: flex; flex-direction: column;">
                      <div style="display: flex; align-items: center; gap: 8px; padding: 7px 11px; background: var(--head); border-bottom: 1px solid rgba(var(--w), 0.07); position: sticky; top: 0;">
                        <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {{ g.tint }};">{{ g.name }}</span>
                        <span style="font-family: var(--font-mono); font-size: 9px; color: var(--tx5);">{{ g.count }}</span>
                      </div>
                      <sc-for list="{{ g.rows }}" as="m" hint-placeholder-count="4">
                        <div onClick="{{ m.pick }}" style="display: flex; align-items: center; gap: 10px; padding: 8px 11px; border-bottom: 1px solid rgba(var(--w), 0.05); cursor: pointer; background: {{ m.bg }}; transition: background 130ms ease;" style-hover="background: rgba(var(--w), 0.05);">
                          <span style="width: 14px; height: 14px; border-radius: 9999px; border: 1px solid {{ m.ring }}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <span style="width: 6px; height: 6px; border-radius: 9999px; background: {{ m.inner }}; transition: background 160ms ease;"></span>
                          </span>
                          <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 11.5px; color: {{ m.color }}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ m.label }}</span>
                          <span style="font-size: 10.5px; color: var(--tx5); white-space: nowrap;">{{ m.meta }}</span>
                        </div>
                      </sc-for>
                    </div>
                  </sc-for>
                  <sc-if value="{{ modal.mergeEmpty }}" hint-placeholder-val="{{ false }}">
                    <span style="display: block; font-size: 12px; color: var(--tx4); padding: 12px;">Aucun compte ne correspond.</span>
                  </sc-if>
                </div>
                <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">{{ modal.mergeText }}</span>
              </div>

              <div style="display: flex; flex-direction: column; gap: 9px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Ajouter un contact</span>
                <input value="{{ modal.alias }}" onChange="{{ modal.onAlias }}" placeholder="Nom court (ex. release)" style="height: 36px; box-sizing: border-box; padding: 0 12px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.12); background: transparent; outline: none; font-family: var(--font-mono); font-size: 12.5px; color: var(--tx1);" />
                <span style="font-size: 12px; color: var(--tx4);">Qui désigne-t-il ? Un agent, ou plusieurs pour un groupe.</span>
                <sc-if value="{{ modal.hasPicked }}" hint-placeholder-val="{{ false }}">
                  <div class="fade-in" style="display: flex; flex-wrap: wrap; gap: 6px;">
                    <sc-for list="{{ modal.picked }}" as="p" hint-placeholder-count="2">
                      <span onClick="{{ p.remove }}" title="Retirer" style="display: inline-flex; align-items: center; gap: 7px; height: 25px; padding: 0 9px; border-radius: 6px; border: 1px solid rgba(var(--w), 0.2); background: rgba(var(--w), 0.07); font-family: var(--font-mono); font-size: 11px; color: var(--tx1); cursor: pointer;">
                        {{ p.label }}
                        <span class="ic" style="width: 10px; height: 10px; color: var(--tx4); -webkit-mask-image: url('./assets/icons/x.svg'); mask-image: url('./assets/icons/x.svg');"></span>
                      </span>
                    </sc-for>
                  </div>
                </sc-if>
                <div style="display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 11px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.12);">
                  <span class="ic" style="width: 13px; height: 13px; color: var(--tx5); -webkit-mask-image: url('./assets/icons/search.svg'); mask-image: url('./assets/icons/search.svg');"></span>
                  <input value="{{ modal.targetQuery }}" onChange="{{ modal.onTargetQuery }}" placeholder="Chercher un agent" style="flex: 1; min-width: 0; border: none; outline: none; background: transparent; font-family: var(--font-mono); font-size: 12px; color: var(--tx1);" />
                  <span style="font-family: var(--font-mono); font-size: 10px; color: var(--tx5); white-space: nowrap;">{{ modal.targetCount }}</span>
                </div>
                <div style="max-height: 176px; overflow-y: auto; border: 1px solid rgba(var(--w), 0.08); border-radius: 8px;">
                  <sc-for list="{{ modal.targetGroups }}" as="g" hint-placeholder-count="2">
                    <div style="display: flex; flex-direction: column;">
                      <div style="display: flex; align-items: center; gap: 8px; padding: 7px 11px; background: var(--head); border-bottom: 1px solid rgba(var(--w), 0.07); position: sticky; top: 0;">
                        <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {{ g.tint }};">{{ g.name }}</span>
                        <span style="font-family: var(--font-mono); font-size: 9px; color: var(--tx5);">{{ g.count }}</span>
                      </div>
                      <sc-for list="{{ g.rows }}" as="t" hint-placeholder-count="4">
                        <div onClick="{{ t.pick }}" style="display: flex; align-items: center; gap: 10px; padding: 8px 11px; border-bottom: 1px solid rgba(var(--w), 0.05); cursor: pointer; background: {{ t.bg }}; transition: background 130ms ease;" style-hover="background: rgba(var(--w), 0.05);">
                          <span style="width: 14px; height: 14px; border-radius: 4px; border: 1px solid {{ t.ring }}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <span class="ic" style="width: 10px; height: 10px; color: {{ t.tickColor }}; -webkit-mask-image: url('./assets/icons/check.svg'); mask-image: url('./assets/icons/check.svg');"></span>
                          </span>
                          <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 11.5px; color: {{ t.color }}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ t.label }}</span>
                          <span style="font-size: 10.5px; color: var(--tx5); white-space: nowrap;">{{ t.meta }}</span>
                        </div>
                      </sc-for>
                    </div>
                  </sc-for>
                  <sc-if value="{{ modal.targetEmpty }}" hint-placeholder-val="{{ false }}">
                    <span style="display: block; font-size: 12px; color: var(--tx4); padding: 12px;">Aucun agent ne correspond.</span>
                  </sc-if>
                </div>
                <input value="{{ modal.note }}" onChange="{{ modal.onNote }}" placeholder="Note (facultatif) : quand lui écrire" style="height: 36px; box-sizing: border-box; padding: 0 12px; border-radius: 8px; border: 1px solid rgba(var(--w), 0.12); background: transparent; outline: none; font-family: var(--font-ui); font-size: 12.5px; color: var(--tx1);" />
              </div>

              <div style="display: flex; flex-direction: column; gap: 8px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Désactiver le compte</span>
                <sc-if value="{{ modal.acct.idle }}" hint-placeholder-val="{{ true }}">
                  <span onClick="{{ modal.acct.askDeactivate }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(190, 18, 60, 0.3); cursor: pointer;" style-hover="background: rgba(190, 18, 60, 0.08);">
                    <span class="ic" style="width: 13px; height: 13px; color: var(--fail-tx); -webkit-mask-image: url('./assets/icons/user-round-x.svg'); mask-image: url('./assets/icons/user-round-x.svg');"></span>
                    <span style="font-size: 12px; color: var(--fail-tx);">Désactiver le compte</span>
                  </span>
                </sc-if>
                <sc-if value="{{ modal.acct.confirming }}" hint-placeholder-val="{{ false }}">
                  <div ref="{{ modal.acct.reveal }}" class="fade-in" style="display: flex; flex-direction: column; gap: 8px; padding: 12px 13px; border: 1px solid rgba(190, 18, 60, 0.32); border-radius: 9px; background: rgba(190, 18, 60, 0.06);">
                    <span style="font-size: 12px; font-weight: 600; color: var(--fail-tx);">Désactiver ce compte ?</span>
                    <span style="font-size: 12px; color: var(--tx3); line-height: 1.55; text-wrap: pretty;">{{ modal.acct.consequence }}</span>
                    <sc-if value="{{ modal.acct.hasWaiting }}" hint-placeholder-val="{{ false }}">
                      <span style="font-size: 12px; color: var(--warn-tx); line-height: 1.55; text-wrap: pretty;">{{ modal.acct.waitingText }}</span>
                    </sc-if>
                    <div style="display: flex; gap: 8px;">
                      <button type="button" onClick="{{ modal.acct.deactivate }}" style="height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(190, 18, 60, 0.4); background: transparent; font-family: var(--font-ui); font-size: 12px; color: var(--fail-tx); cursor: pointer;">Désactiver</button>
                      <button type="button" onClick="{{ modal.acct.cancelDeactivate }}" style="height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.12); background: transparent; font-family: var(--font-ui); font-size: 12px; color: var(--tx3); cursor: pointer;">Annuler</button>
                    </div>
                    <sc-if value="{{ modal.acct.noticeAtDeactivate }}" hint-placeholder-val="{{ false }}">
                      <span role="alert" style="font-size: 11.5px; color: var(--fail-tx); line-height: 1.5;">{{ modal.acct.notice }}</span>
                    </sc-if>
                  </div>
                </sc-if>
              </div>
            </div>
          </sc-if>

          <sc-if value="{{ modal.isPoste }}" hint-placeholder-val="{{ false }}">
            <section style="display: flex; flex-direction: column; gap: 10px; padding-bottom: 16px;">
              <span style="font-size: 12px; font-weight: 600; color: var(--tx2);">Reprise et conservation</span>
              <div style="display: flex; gap: 8px;">
                <button type="button" onClick="{{ modal.previewMigration }}">Reprendre une ancienne boîte</button>
                <button type="button" onClick="{{ modal.previewRetention }}">Voir ce qui peut être supprimé</button>
              </div>
              <sc-if value="{{ modal.hasMigration }}">
                <div style="max-height: 180px; overflow-y: auto;">
                  <sc-for list="{{ modal.migrationRows }}" as="row"><p style="font-size: 11px; color: var(--tx3);">{{ row.account }} · {{ row.counts }}</p></sc-for>
                </div>
              </sc-if>
              <sc-if value="{{ modal.hasMigration || modal.hasRetention }}">
                <span style="font-size: 12px; color: var(--tx3);">{{ modal.maintenanceSummary }}</span>
                <span style="font-size: 11px; color: var(--tx4);">Aucune suppression avant un an. Les données encore référencées et celles non intégrées par une installation active sont protégées.</span>
                <div style="display: flex; gap: 8px;">
                  <button type="button" onClick="{{ modal.cancelMaintenance }}">Renoncer</button>
                  <button type="button" onClick="{{ modal.applyMaintenance }}">Confirmer cet aperçu</button>
                </div>
              </sc-if>
              <span style="font-size: 12px; color: var(--pass-tx);">{{ modal.maintenanceNotice }}</span>
            </section>
            <div style="display: flex; flex-direction: column; gap: 16px;">
              <div style="display: flex; flex-direction: column; gap: 8px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">La boîte de cet ordinateur</span>
                <span title="{{ boxPath }}" style="font-family: var(--font-mono); font-size: 11px; color: var(--tx3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ boxPath }}</span>
                <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">Choisis un dossier local, un partage réseau ou la même URL HTTPS sur chaque ordinateur. Le courrier de chaque boîte reste séparé.</span>
                <div onClick="{{ modal.browse }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 30px; padding: 0 12px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.14); cursor: pointer;" style-hover="background: rgba(var(--w), 0.06);">
                  <span class="ic" style="width: 13px; height: 13px; color: var(--tx2); -webkit-mask-image: url('./assets/icons/folder-symlink.svg'); mask-image: url('./assets/icons/folder-symlink.svg');"></span>
                  <span style="font-size: 12.5px; color: var(--tx1);">Choisir un dossier local ou partagé</span>
                </div>
                <label style="display: flex; flex-direction: column; gap: 5px; font-size: 11px; color: var(--tx3);">Adresse de la boîte en ligne
                  <input type="url" value="{{ modal.remoteUrl }}" onChange="{{ modal.onRemoteUrl }}" placeholder="https://messenger.arka-squad.app" autocomplete="url" style="height: 36px; box-sizing: border-box; padding: 0 10px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.14); background: transparent; color: var(--tx1); font-family: var(--font-mono); font-size: 11px;" />
                </label>
                <label style="display: flex; flex-direction: column; gap: 5px; font-size: 11px; color: var(--tx3);">Clé d’accès privée de cette boîte
                  <input type="password" value="{{ modal.remoteToken }}" onChange="{{ modal.onRemoteToken }}" placeholder="Clé fournie par l’administrateur" autocomplete="off" style="height: 36px; box-sizing: border-box; padding: 0 10px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.14); background: transparent; color: var(--tx1); font-family: var(--font-mono); font-size: 11px;" />
                </label>
                <button type="button" onClick="{{ modal.connectRemote }}">Connecter l’URL HTTPS</button>
                <sc-if value="{{ modal.exchangeNotice }}" hint-placeholder-val="{{ false }}">
                  <span style="font-size: 12px; color: var(--warn-tx); line-height: 1.5;">{{ modal.exchangeNotice }}</span>
                </sc-if>
              </div>
              <div style="display: flex; flex-direction: column; gap: 9px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Outils d'IA de cet ordinateur</span>
                <sc-for list="{{ modal.hosts }}" as="h" hint-placeholder-count="5">
                  <div onClick="{{ h.act }}" title="{{ h.title }}" style="display: flex; align-items: center; gap: 10px; padding: 9px 10px; border: 1px solid rgba(var(--w), 0.08); border-radius: 8px; cursor: {{ h.cursor }};">
                    <span class="ic" style="width: 14px; height: 14px; color: {{ h.color }}; -webkit-mask-image: url('{{ h.icon }}'); mask-image: url('{{ h.icon }}');"></span>
                    <span style="flex: 1; min-width: 0; font-size: 12.5px; color: var(--tx2);">{{ h.name }}</span>
                    <span style="font-size: 11.5px; color: {{ h.color }}; white-space: nowrap;">{{ h.state }}</span>
                  </div>
                </sc-for>
                <sc-if value="{{ modal.providerNotice }}" hint-placeholder-val="{{ false }}">
                  <span style="font-size: 11.5px; color: var(--fail-tx); line-height: 1.5;">{{ modal.providerNotice }}</span>
                </sc-if>
                <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">Branche la boîte dans ces outils, sans effacer leurs réglages. Ouvre une nouvelle session dans chaque outil pour charger les outils MCP, puis colle l’invite : chaque agent crée son compte.</span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 8px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Surveillance par Cortex</span>
                <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">Cortex lit en lecture seule les projets cochés, rien d’autre. Rien n’est surveillé par défaut.</span>
                <sc-for list="{{ modal.watch.projects }}" as="p" hint-placeholder-count="2">
                  <div onClick="{{ p.toggle }}" style="display: flex; align-items: center; gap: 10px; padding: 7px 10px; border: 1px solid rgba(var(--w), 0.08); border-radius: 8px; cursor: pointer;">
                    <span style="font-size: 13px; color: {{ p.color }};">{{ p.mark }}</span>
                    <span style="flex: 1; min-width: 0; font-size: 12.5px; color: var(--tx2);">{{ p.name }}</span>
                  </div>
                </sc-for>
                <span style="font-size: 12px; color: var(--tx3);">{{ modal.watch.stateText }}</span>
                <div style="display: flex; gap: 8px;">
                  <button type="button" onClick="{{ modal.watch.open }}">{{ modal.watch.openLabel }}</button>
                  <sc-if value="{{ modal.watch.canPause }}" hint-placeholder-val="{{ false }}">
                    <button type="button" onClick="{{ modal.watch.pause }}">{{ modal.watch.pauseLabel }}</button>
                    <button type="button" onClick="{{ modal.watch.revoke }}">Retirer l’accès</button>
                  </sc-if>
                </div>
                <sc-if value="{{ modal.watch.key }}" hint-placeholder-val="{{ false }}">
                  <span style="font-size: 11.5px; color: var(--warn-tx); line-height: 1.5;">Clé copiée : colle-la dans Cortex. Elle ne sera plus affichée.</span>
                  <span style="font-family: var(--font-mono); font-size: 11px; color: var(--tx2); word-break: break-all; user-select: all;">{{ modal.watch.key }}</span>
                </sc-if>
                <span style="font-size: 11px; color: var(--tx4); line-height: 1.5;">Délégués de l’Owner : leurs décisions s’affichent « sous délégation ».</span>
                <div style="max-height: 150px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px;">
                  <sc-for list="{{ modal.watch.delegates }}" as="d" hint-placeholder-count="2">
                    <div onClick="{{ d.toggle }}" style="display: flex; align-items: center; gap: 10px; padding: 5px 10px; border-radius: 7px; cursor: pointer;" style-hover="background: rgba(var(--w), 0.06);">
                      <span style="font-size: 13px; color: {{ d.color }};">{{ d.mark }}</span>
                      <span style="flex: 1; min-width: 0; font-family: var(--font-mono); font-size: 11px; color: var(--tx2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ d.address }}</span>
                    </div>
                  </sc-for>
                </div>
                <sc-for list="{{ modal.watch.log }}" as="e" hint-placeholder-count="2">
                  <span style="font-size: 11px; color: var(--tx4);">{{ e.line }}</span>
                </sc-for>
              </div>
              <div style="display: flex; flex-direction: column; gap: 8px;">
                <span style="font-family: var(--font-mono); font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tx5);">Éteindre</span>
                <span style="font-size: 12px; color: var(--tx4); line-height: 1.55; text-wrap: pretty;">Ferme Messenger sur cet ordinateur. Ses outils seront de nouveau disponibles lorsque tu le rouvriras.</span>
                <div onClick="{{ modal.shutdown }}" style="display: inline-flex; align-self: flex-start; align-items: center; gap: 8px; height: 30px; padding: 0 12px; border-radius: 7px; border: 1px solid rgba(190, 18, 60, 0.4); cursor: pointer;" style-hover="background: rgba(190, 18, 60, 0.1);">
                  <span class="ic" style="width: 13px; height: 13px; color: var(--fail-tx); -webkit-mask-image: url('./assets/icons/power.svg'); mask-image: url('./assets/icons/power.svg');"></span>
                  <span style="font-size: 12.5px; color: var(--fail-tx);">Éteindre la boîte</span>
                </div>
              </div>
            </div>
          </sc-if>
        </div>

        <div style="display: flex; align-items: center; gap: 10px; padding: 14px 20px; border-top: 1px solid rgba(var(--w), 0.07); background: var(--head);">
          <span style="flex: 1; min-width: 0; font-size: 11.5px; color: var(--tx5); line-height: 1.45; text-wrap: pretty;">{{ modal.foot }}</span>
          <span onClick="{{ closeModal }}" style="display: inline-flex; align-items: center; height: 31px; padding: 0 13px; border-radius: 7px; border: 1px solid rgba(var(--w), 0.12); font-size: 12.5px; color: var(--tx3); cursor: pointer; white-space: nowrap;" style-hover="background: rgba(var(--w), 0.05);">{{ modal.cancel }}</span>
          <sc-if value="{{ modal.hasPrimary }}" hint-placeholder-val="{{ true }}">
            <span onClick="{{ modal.primary }}" style="display: inline-flex; align-items: center; gap: 8px; height: 31px; padding: 0 14px; border-radius: 7px; border: 1px solid {{ modal.primaryBorder }}; background: {{ modal.primaryBg }}; font-size: 12.5px; font-weight: 500; color: {{ modal.primaryColor }}; cursor: pointer; white-space: nowrap; transition: background 140ms ease;" style-hover="background: rgba(var(--w), 0.1);">
              <span class="ic" style="width: 13px; height: 13px; -webkit-mask-image: url('{{ modal.primaryIcon }}'); mask-image: url('{{ modal.primaryIcon }}');"></span>
              {{ modal.primaryLabel }}
            </span>
          </sc-if>
        </div>
      </div>
    </div>
  </sc-if>
</div>
