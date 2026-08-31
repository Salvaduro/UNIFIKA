import React from 'react';

const ConfirmModal = ({ isOpen, title, message, onConfirm, onCancel, confirmText = "Aceptar", cancelText = "Cancelar", isDestructive = false }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-[#12121A] border border-[#2A2A35] rounded-xl shadow-2xl max-w-md w-full overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="p-6">
          <h3 className="text-xl font-semibold text-white mb-2">{title}</h3>
          <p className="text-[#A1A1AA] text-sm">{message}</p>
        </div>
        <div className="px-6 py-4 bg-[#0A0A0F] border-t border-[#2A2A35] flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm font-medium text-[#A1A1AA] hover:text-white hover:bg-[#2A2A35] transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors shadow-lg ${
              isDestructive 
                ? "bg-red-500 hover:bg-red-600 shadow-red-500/20" 
                : "bg-blue-600 hover:bg-blue-700 shadow-blue-500/20"
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmModal;
