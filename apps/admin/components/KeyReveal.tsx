'use client'

import type { ApproveResponse } from '@vision-hub/contracts'
import { Banner, Button, CopyField, Modal, Pill } from '@vision-hub/ui'

/** Shown after approval or rotation -- the one moment the full key is on screen here. */
export function KeyReveal({ result, onClose }: { result: ApproveResponse; onClose: () => void }) {
  return (
    <Modal
      title={result.minted ? 'Key issued' : 'Key already issued'}
      onClose={onClose}
      footer={<Button onClick={onClose}>Done</Button>}
    >
      <Banner kind={result.minted ? 'success' : 'info'} className="mt-0">
        {result.minted ? (
          <>
            <strong>{result.user.email}</strong> is approved. Their account page shows this key now, live.
          </>
        ) : (
          <>
            <strong>{result.user.email}</strong> already had an active key, so no second one was minted.
          </>
        )}
      </Banner>
      <CopyField label="Licence key" value={result.key.key} />
      <p className="text-[13px] text-faint">
        Tier <Pill status={result.key.tier} /> · they paste this into the desktop app under Settings → Licence.
      </p>
    </Modal>
  )
}
